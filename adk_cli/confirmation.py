from typing import Optional, Callable, Awaitable, Any, Dict
import json


class ConfirmationManager:
    """Manages pending confirmation requests between the agent tools and the TUI."""

    def __init__(self):
        self._request_callback: Optional[
            Callable[
                [str, str, Optional[str], Optional[Dict[str, Any]]], Awaitable[bool]
            ]
        ] = None

    @property
    def has_callback(self) -> bool:
        """Return True if a UI callback is registered."""
        return self._request_callback is not None

    def register_callback(
        self,
        callback: Callable[
            [str, str, Optional[str], Optional[Dict[str, Any]]], Awaitable[bool]
        ],
    ):
        """Register a callback to be called when a confirmation is requested."""
        self._request_callback = callback

    async def request_confirmation(
        self,
        hint: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Called by a tool or plugin to request confirmation from the user."""
        # If we have a TUI callback, use it directly as it returns the result.
        if self._request_callback:
            return await self._request_callback("current", hint, tool_name, tool_args)

        # If we are in a TTY (CLI mode), ask using a Click prompt.
        import sys

        if sys.stdin.isatty():
            try:
                import click

                msg = f"\n⚠️  {hint}"
                if tool_name:
                    msg += f"\nTool: {tool_name}"
                if tool_args:
                    msg += f"\nArgs: {json.dumps(tool_args, indent=2)}"

                # Use a separate thread if needed, but since we are in the runner loop,
                # a simple blocking call is often acceptable for CLI mode.
                return click.confirm(f"{msg}\nProceed?", default=True)
            except ImportError:
                pass

        # If we reach here, we have no interactive way to ask.
        # This will result in an error in the runner, which is what we want.
        return False


# Global singleton
confirmation_manager = ConfirmationManager()
