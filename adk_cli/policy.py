from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional, Dict
from rich.text import Text
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from adk_cli.confirmation import confirmation_manager
from adk_cli.summarize import summarize_tool_call
from adk_cli.models import ToolPolicy, ConfirmationResult

# Tools that are considered safe and don't require confirmation in 'ask' mode
# Deprecated: use @tool_metadata(ToolPolicy.READ_ONLY, ...) instead
READ_ONLY_TOOLS = {
    "ls",
    "list_dir",
    "cat",
    "view_file",
    "view_file_outline",
    "grep",
    "grep_search",
    "find",
    "find_by_name",
    "read_url_content",
    "read_many_files",
    "load_skill",
    "load_skill_resource",
    "manage_todo_list",
    "explore_codebase",
    "review_work",
}

SAFE_BASH_COMMANDS = {
    "git status",
    "git log",
    "git diff",
    "git branch",
    "pwd",
    "whoami",
    "hostname",
    "python --version",
    "python3 --version",
    "pip --version",
    "uv --version",
    "date",
}


class PermissionMode(str, Enum):
    PLAN = "plan"
    AUTO = "auto"
    ASK = "ask"


class PolicyOutcome(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass
class PolicyCheckResult:
    outcome: PolicyOutcome
    reason: str


class BasePolicyEngine:
    """Base class for policy evaluation."""

    async def evaluate(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tool: Optional[BaseTool] = None,
    ) -> PolicyCheckResult:
        return PolicyCheckResult(outcome=PolicyOutcome.ALLOW, reason="Default allow")


class CustomPolicyEngine(BasePolicyEngine):
    """
    Implements the core policy logic for adk-cli.
    Maps tool calls to outcomes based on PermissionMode and tool sensitivity.
    """

    def __init__(self, mode: PermissionMode = PermissionMode.ASK):
        self.mode = mode
        self._session_permissions: Dict[str, set] = {}

    def _format_reason(
        self, prefix: str, tool_name: str, tool_args: Dict[str, Any]
    ) -> str:
        # The reason is shown in a Label, which doesn't support Rich markup.
        # We should use the summary but without the markup tags.
        summary = summarize_tool_call(tool_name, tool_args)
        return f"{prefix}: {Text.from_markup(summary).plain}"

    def allow_for_session(self, tool_name: str, tool_args: Dict[str, Any]):
        """
        Grant session-wide permission for a tool with optional granular arguments.

        CUSTOMIZATION POINT:
        To add new granular permission logic for a specific tool:
        1. Add an `elif tool_name == "your_tool":` block here to extract
           the identifying attribute (e.g., path, command, etc.)
        2. Ensure the same attribute is checked in `_is_session_allowed`.
        """
        if tool_name not in self._session_permissions:
            self._session_permissions[tool_name] = set()

        # Specific granular permissions based on tool type
        if tool_name == "bash":
            cmd = tool_args.get("command", "").strip()
            if cmd:
                self._session_permissions[tool_name].add(cmd)
        elif tool_name in ["edit_file", "write_file", "cat"]:
            path = tool_args.get("path")
            if path:
                self._session_permissions[tool_name].add(path)
        else:
            # Generic 'allow all for this tool'
            self._session_permissions[tool_name].add("*")

    def _is_session_allowed(self, tool_name: str, tool_args: Dict[str, Any]) -> bool:
        """
        Check if a tool call is already allowed for this session.

        CUSTOMIZATION POINT:
        When adding granular logic to `allow_for_session`, you must
        also update this method to correctly check the identifier.
        """
        if tool_name not in self._session_permissions:
            return False

        allowed_items = self._session_permissions[tool_name]
        if "*" in allowed_items:
            return True

        if tool_name == "bash":
            cmd = tool_args.get("command", "").strip()
            return cmd in allowed_items

        if tool_name in ["edit_file", "write_file", "cat"]:
            path = tool_args.get("path")
            return path in allowed_items

        return False

    async def evaluate(
        self, tool_name: str, tool_args: Dict[str, Any], tool: Optional[BaseTool] = None
    ) -> PolicyCheckResult:
        if self.mode == PermissionMode.AUTO:
            return PolicyCheckResult(
                outcome=PolicyOutcome.ALLOW, reason="Auto-approval mode"
            )

        # 1. Check for metadata on the tool
        if tool and hasattr(tool, "callable") and tool.callable:
            metadata = getattr(tool.callable, "_adk_tool_metadata", None)
            if metadata:
                if metadata.policy == ToolPolicy.READ_ONLY:
                    return PolicyCheckResult(
                        outcome=PolicyOutcome.ALLOW, reason="Read-only operation"
                    )
                if metadata.policy == ToolPolicy.CONDITIONAL:
                    if metadata.conditional_check and metadata.conditional_check(
                        tool_args
                    ):
                        return PolicyCheckResult(
                            outcome=PolicyOutcome.ALLOW, reason="Safe conditional call"
                        )

        # 2. Check deprecated hardcoded lists for backwards compatibility or tools without metadata
        if tool_name in READ_ONLY_TOOLS:
            return PolicyCheckResult(
                outcome=PolicyOutcome.ALLOW, reason="Read-only operation"
            )

        if self._is_session_allowed(tool_name, tool_args):
            return PolicyCheckResult(
                outcome=PolicyOutcome.ALLOW, reason="Session-wide allowance"
            )

        if tool_name == "bash":
            cmd = tool_args.get("command", "").strip()
            if cmd in SAFE_BASH_COMMANDS:
                return PolicyCheckResult(
                    outcome=PolicyOutcome.ALLOW, reason="Safe bash command"
                )

        if self.mode == PermissionMode.PLAN:
            # In 'plan' mode, we might want to confirm everything or just log it.
            # For now, treat it similarly to 'ask' but with different messaging.
            return PolicyCheckResult(
                outcome=PolicyOutcome.CONFIRM,
                reason=self._format_reason(
                    "Planned execution of", tool_name, tool_args
                ),
            )

        # Fallback for ASK mode or any unexpected mode
        return PolicyCheckResult(
            outcome=PolicyOutcome.CONFIRM,
            reason=self._format_reason("Sensitive tool call", tool_name, tool_args),
        )


class SecurityPlugin(BasePlugin):
    """
    ADK Plugin that enforces security policies before tool execution.
    """

    def __init__(self, policy_engine: BasePolicyEngine):
        super().__init__(name="security")
        self.policy_engine = policy_engine

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: Dict[str, Any], tool_context: ToolContext
    ) -> Optional[Dict[str, Any]]:
        """
        Intercepts tool calls and evaluates them against the policy engine.
        """
        # If the tool has already been confirmed in this context, allow it.
        if tool_context.tool_confirmation and tool_context.tool_confirmation.confirmed:
            return None

        result = await self.policy_engine.evaluate(tool.name, tool_args, tool=tool)

        if result.outcome == PolicyOutcome.DENY:
            return {"error": f"Policy Denied: {result.reason}"}

        if result.outcome == PolicyOutcome.CONFIRM:
            # Always notify the ADK context about the confirmation request
            tool_context.request_confirmation(hint=result.reason)

            # Let the confirmation manager handle it (it knows about current TUI/CLI)
            # Response: ConfirmationResult
            approved_result = await confirmation_manager.request_confirmation(
                hint=result.reason, tool_name=tool.name, tool_args=tool_args
            )

            if approved_result != ConfirmationResult.DENIED:
                if approved_result == ConfirmationResult.APPROVED_SESSION:
                    # Update policy engine for session-wide allowance
                    if isinstance(self.policy_engine, CustomPolicyEngine):
                        self.policy_engine.allow_for_session(tool.name, tool_args)
                return None  # Approved! Continue execution!
            else:
                return {
                    "error": f"User denied execution of {tool.name}. Do not retry this exact tool call without asking the user for clarification or modifying the arguments."
                }

        return None
