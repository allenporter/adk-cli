"""Global settings storage for adk-cli.

Settings are persisted to ~/.adk/settings.json, mirroring the approach
used by gemini-cli which stores settings in ~/.gemini/.
"""

import json
import os
from pathlib import Path
from typing import Any

ADK_DIR = ".adk"


def get_global_adk_dir() -> Path:
    """Return the global adk-cli config directory (~/.adk/)."""
    home = Path(os.path.expanduser("~"))
    return home / ADK_DIR


def get_global_settings_path() -> Path:
    """Return the path to the global settings file (~/.adk/settings.json)."""
    return get_global_adk_dir() / "settings.json"


def get_local_settings_path(project_root: Path) -> Path:
    """Return the path to the local settings file (<project-root>/.adk/settings.json)."""
    return project_root / ADK_DIR / "settings.json"


def load_settings(project_root: Path | None = None) -> dict[str, Any]:
    """Load settings by merging global settings with project-specific overrides.

    If project_root is provided, local settings in <project-root>/.adk/settings.json
    override global settings in ~/.adk/settings.json.
    """
    settings = load_global_settings()

    if project_root:
        local_settings = load_local_settings(project_root)
        settings.update(local_settings)

    return settings


def load_global_settings() -> dict[str, Any]:
    """Load settings from the global settings file (~/.adk/settings.json)."""
    return _load_file(get_global_settings_path())


def load_local_settings(project_root: Path) -> dict[str, Any]:
    """Load settings from a local settings file (<project-root>/.adk/settings.json)."""
    return _load_file(get_local_settings_path(project_root))


def _load_file(path: Path) -> dict[str, Any]:
    """Helper to load a JSON file."""
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8")
        result: dict[str, Any] = json.loads(content)
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(settings: dict[str, Any]) -> None:
    """Persist settings to the global settings file (~/.adk/settings.json).

    adk-cli CLI commands exclusively manage global settings.
    Local overrides must be edited manually in the project directory.
    """
    path = get_global_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )
