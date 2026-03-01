from enum import Enum, auto
from typing import Any, Callable, Dict, Optional


class ToolPolicy(Enum):
    """
    Defines the security policy for a tool.
    """

    READ_ONLY = auto()
    """Safe to execute without confirmation (e.g., ls, cat)."""

    SENSITIVE = auto()
    """Requires confirmation before execution (e.g., write_file, edit_file)."""

    CONDITIONAL = auto()
    """Policy depends on tool arguments (e.g., bash)."""


class ConfirmationResult(Enum):
    """
    The result of a user confirmation request.
    """

    DENIED = 0
    """The user denied the execution."""

    APPROVED_ONCE = 1
    """The user approved this specific execution."""

    APPROVED_SESSION = 2
    """The user approved this tool/argument combination for the entire session."""


class ToolMetadata:
    """
    Metadata attached to tool functions via the @tool_metadata decorator.
    """

    def __init__(
        self,
        policy: ToolPolicy,
        summary_template: str,
        conditional_check: Optional[Callable[[Dict[str, Any]], bool]] = None,
    ):
        self.policy = policy
        self.summary_template = summary_template
        self.conditional_check = conditional_check
