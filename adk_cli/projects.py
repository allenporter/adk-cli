"""Project detection and Short ID mapping for adk-cli.

Maps workspace directories to unique, human-readable Short IDs to allow
context-aware session persistence.
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Optional

from adk_cli.settings import get_global_adk_dir

logger = logging.getLogger(__name__)

PROJECTS_FILE = "projects.json"
WORKSPACE_MARKERS = {
    ".git",
    "pyproject.toml",
    "package.json",
    "setup.py",
}


def find_project_root(start_path: Optional[Path] = None) -> Path:
    """
    Search upwards from start_path to find a project root marker.
    Prioritizes .git as the strongest indicator of a repo root.
    Returns start_path (resolved) if no marker is found.
    """
    current = (start_path or Path.cwd()).resolve()

    # Priority 1: Check for .git specifically to find the repo root
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent

    # Priority 2: Check for other common markers
    for parent in [current, *current.parents]:
        if any((parent / marker).exists() for marker in WORKSPACE_MARKERS):
            return parent

    return current


def _load_project_registry() -> dict[str, str]:
    """Loads the path-to-id mapping from ~/.adk/projects.json."""
    registry_path = get_global_adk_dir() / PROJECTS_FILE
    if not registry_path.exists():
        return {}
    try:
        return json.loads(registry_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_project_registry(registry: dict[str, str]) -> None:
    """Saves the path-to-id mapping to ~/.adk/projects.json."""
    registry_path = get_global_adk_dir() / PROJECTS_FILE
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")


def get_project_id(project_root: Path) -> str:
    """
    Returns the Short ID for a project root, generating a new one if necessary.
    """
    path_str = str(project_root.resolve())
    registry = _load_project_registry()

    if path_str in registry:
        return registry[path_str]

    # Generate a new ID. Using a short hash for now.
    # In the future, this could be more "human-readable" like gemini-cli.
    new_id = hashlib.sha256(path_str.encode()).hexdigest()[:6]

    # Ensure uniqueness (unlikely collision for 6 chars in small registry)
    while new_id in registry.values():
        new_id = hashlib.sha256((path_str + new_id).encode()).hexdigest()[:6]

    registry[path_str] = new_id
    _save_project_registry(registry)
    return new_id


def get_session_db_path() -> Path:
    """Returns the path to the global sessions SQLite database."""
    return get_global_adk_dir() / "sessions.db"
