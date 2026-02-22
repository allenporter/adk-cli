import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class StatusManager:
    """Manages system-level status updates (e.g. rate limit retries) for the UI."""

    def __init__(self):
        self._callback: Optional[Callable[[str], None]] = None

    def register_callback(self, callback: Callable[[str], None]):
        """Register a callback for status messages."""
        self._callback = callback

    def update(self, message: str):
        """Update the current status message."""
        logger.debug(f"Status Update: {message}")
        if self._callback:
            self._callback(message)


status_manager = StatusManager()
