import os
import portalocker
import psutil
from pathlib import Path
import logging

from adk_cli.projects import get_global_adk_dir

logger = logging.getLogger(__name__)


def get_lock_dir() -> Path:
    lock_dir = get_global_adk_dir() / "locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir


def is_session_locked(session_id: str) -> bool:
    """Checks if a session is currently locked by an active process."""
    lock_path = get_lock_dir() / f"{session_id}.lock"
    if not lock_path.exists():
        return False

    try:
        with open(lock_path, "r") as f:
            pid_str = f.read().strip()
            if not pid_str:
                return False
            pid = int(pid_str)

        # Check if process is still running
        if psutil.pid_exists(pid):
            # Double check it's actually an adk process (optional but safer)
            return True
        else:
            # Stale lock
            return False
    except (ValueError, OSError):
        return False


class SessionLock:
    """Context manager for managing a session lock."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.lock_path = get_lock_dir() / f"{session_id}.lock"
        self._lock_file = None

    def __enter__(self):
        try:
            # We use portalocker for cross-platform file locking
            self._lock_file = open(self.lock_path, "w")
            portalocker.lock(self._lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            logger.debug(f"Locked session {self.session_id}")
        except (portalocker.exceptions.LockException, IOError):
            raise RuntimeError(
                f"Session {self.session_id} is already in use by another process."
            )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._lock_file:
            try:
                portalocker.unlock(self._lock_file)
                self._lock_file.close()
                if self.lock_path.exists():
                    os.remove(self.lock_path)
            except Exception as e:
                logger.warning(f"Failed to release lock for {self.session_id}: {e}")


class StatusManager:
    """Manages real-time status updates (e.g. rate limit retries) shown in the TUI."""

    def __init__(self):
        self._callback = None

    def register_callback(self, callback):
        self._callback = callback

    def update(self, message: str):
        if self._callback:
            self._callback(message)


status_manager = StatusManager()
