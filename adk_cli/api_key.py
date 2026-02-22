"""API key loading, saving, and environment file support for adk-cli.

Priority order for API key resolution:
  1. GOOGLE_API_KEY environment variable
  2. GEMINI_API_KEY environment variable
  3. api_key field in ~/.adk/settings.json

This mirrors the approach used by gemini-cli, which reads GEMINI_API_KEY
from the environment or from OS keychain / ~/.gemini/ storage.
"""

import os
from pathlib import Path

import dotenv

from adk_cli.settings import get_global_adk_dir, load_settings, save_settings

_ENV_VARS = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
_SETTINGS_KEY = "api_key"


def load_api_key() -> str | None:
    """Load the Gemini API key from environment variables or persisted settings.

    Checks (in order):
      1. GOOGLE_API_KEY env var
      2. GEMINI_API_KEY env var
      3. api_key entry in ~/.adk/settings.json

    Returns the key string, or None if no key is found.
    """
    for var in _ENV_VARS:
        value = os.environ.get(var)
        if value and value.strip():
            return value.strip()

    settings = load_settings()
    stored: str | None = settings.get(_SETTINGS_KEY)
    if stored and stored.strip():
        return stored.strip()

    return None


def save_api_key(api_key: str) -> None:
    """Persist the given API key to ~/.adk/settings.json.

    The key is stored under the ``api_key`` field in the settings dict.
    """
    settings = load_settings()
    settings[_SETTINGS_KEY] = api_key.strip()
    save_settings(settings)


def load_env_file(workspace_dir: str | None = None) -> None:
    """Load environment variables from a .env file, if one is found.

    Search order:
      1. <workspace_dir>/.adk/.env
      2. <workspace_dir>/.env
      3. ~/.adk/.env

    Variables already set in the environment are not overwritten, matching
    the behaviour of gemini-cli's ``loadEnvironment()``.
    """
    candidates: list[Path] = []

    if workspace_dir:
        workspace = Path(workspace_dir)
        candidates.append(workspace / ".adk" / ".env")
        candidates.append(workspace / ".env")

    candidates.append(get_global_adk_dir() / ".env")

    for candidate in candidates:
        if candidate.is_file():
            # override=False means existing env vars are not overwritten
            dotenv.load_dotenv(candidate, override=False)
            break
