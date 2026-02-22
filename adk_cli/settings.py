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


def load_settings() -> dict[str, Any]:
    """Load settings from the global settings file.

    Returns an empty dict if the file doesn't exist yet.
    """
    settings_path = get_global_settings_path()
    if not settings_path.exists():
        return {}
    try:
        content = settings_path.read_text(encoding="utf-8")
        result: dict[str, Any] = json.loads(content)
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(settings: dict[str, Any]) -> None:
    """Persist settings to the global settings file.

    Creates the directory if it doesn't exist.
    """
    settings_path = get_global_settings_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )
