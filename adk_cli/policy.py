from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional, Dict
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

from adk_cli.confirmation import confirmation_manager

# Tools that are considered safe and don't require confirmation in 'ask' mode
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
        self, tool_name: str, tool_args: Dict[str, Any]
    ) -> PolicyCheckResult:
        return PolicyCheckResult(outcome=PolicyOutcome.ALLOW, reason="Default allow")


class CustomPolicyEngine(BasePolicyEngine):
    """
    Implements the core policy logic for adk-cli.
    Maps tool calls to outcomes based on PermissionMode and tool sensitivity.
    """

    def __init__(self, mode: PermissionMode = PermissionMode.ASK):
        self.mode = mode

    def _format_reason(
        self, prefix: str, tool_name: str, tool_args: Dict[str, Any]
    ) -> str:
        reason = f"{prefix}: {tool_name}"

        # Extract key arguments to surface in the confirmation dialog
        key_args = []
        if "path" in tool_args:
            key_args.append(f"path='{tool_args['path']}'")
        elif "directory" in tool_args:
            key_args.append(f"dir='{tool_args['directory']}'")

        if "command" in tool_args:
            key_args.append(f"cmd='{tool_args['command']}'")

        if "pattern" in tool_args:
            key_args.append(f"pattern='{tool_args['pattern']}'")

        if key_args:
            reason += f" ({', '.join(key_args)})"

        return reason

    async def evaluate(
        self, tool_name: str, tool_args: Dict[str, Any]
    ) -> PolicyCheckResult:
        if self.mode == PermissionMode.AUTO:
            return PolicyCheckResult(
                outcome=PolicyOutcome.ALLOW, reason="Auto-approval mode"
            )

        if tool_name in READ_ONLY_TOOLS:
            return PolicyCheckResult(
                outcome=PolicyOutcome.ALLOW, reason="Read-only operation"
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

        result = await self.policy_engine.evaluate(tool.name, tool_args)

        if result.outcome == PolicyOutcome.DENY:
            return {"error": f"Policy Denied: {result.reason}"}

        if result.outcome == PolicyOutcome.CONFIRM:
            # Always notify the ADK context about the confirmation request
            tool_context.request_confirmation(hint=result.reason)

            # Let the confirmation manager handle it (it knows about current TUI/CLI)
            approved = await confirmation_manager.request_confirmation(
                hint=result.reason, tool_name=tool.name, tool_args=tool_args
            )
            if approved:
                return None  # Approved! Continue execution!
            else:
                return {"error": f"Confirmation required: {result.reason}"}

        return None
