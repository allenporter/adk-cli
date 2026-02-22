"""Tests for adk_cli.api_key module."""

import os
import pytest
from pathlib import Path
from unittest.mock import patch

from adk_cli.api_key import load_api_key, save_api_key, load_env_file


@pytest.fixture(autouse=True)
def clear_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure API key env vars are unset for each test."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_load_api_key_from_google_api_key_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key-abc")
    settings_path = tmp_path / ".adk" / "settings.json"

    with (
        patch("adk_cli.api_key.get_global_adk_dir", return_value=tmp_path / ".adk"),
        patch("adk_cli.settings.get_global_settings_path", return_value=settings_path),
    ):
        result = load_api_key()

    assert result == "google-key-abc"


def test_load_api_key_from_gemini_api_key_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key-xyz")
    settings_path = tmp_path / ".adk" / "settings.json"

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_api_key()

    assert result == "gemini-key-xyz"


def test_load_api_key_google_takes_precedence_over_gemini(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "google-wins")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-loses")
    settings_path = tmp_path / ".adk" / "settings.json"

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_api_key()

    assert result == "google-wins"


def test_load_api_key_from_settings_when_no_env(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    import json

    settings_path.write_text(json.dumps({"api_key": "stored-key-999"}))

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_api_key()

    assert result == "stored-key-999"


def test_load_api_key_returns_none_when_no_source(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_api_key()

    assert result is None


def test_save_api_key_persists_to_settings(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        save_api_key("new-saved-key")
        result = load_api_key()  # reads from settings since no env var

    assert result == "new-saved-key"


def test_save_api_key_strips_whitespace(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        save_api_key("  padded-key  ")
        result = load_api_key()

    assert result == "padded-key"


def test_load_env_file_loads_workspace_dotadk_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".adk" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("GOOGLE_API_KEY=from-env-file\n")

    with patch("adk_cli.api_key.get_global_adk_dir", return_value=tmp_path / ".adk"):
        load_env_file(workspace_dir=str(tmp_path))

    assert os.environ.get("GOOGLE_API_KEY") == "from-env-file"
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)


def test_load_env_file_does_not_overwrite_existing_env_var(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "already-set")
    env_file = tmp_path / ".adk" / ".env"
    env_file.parent.mkdir(parents=True)
    env_file.write_text("GOOGLE_API_KEY=should-not-override\n")

    with patch("adk_cli.api_key.get_global_adk_dir", return_value=tmp_path / ".adk"):
        load_env_file(workspace_dir=str(tmp_path))

    assert os.environ.get("GOOGLE_API_KEY") == "already-set"


def test_load_env_file_no_op_when_no_file_found(tmp_path: Path) -> None:
    """Should not raise when no .env file exists anywhere."""
    with patch("adk_cli.api_key.get_global_adk_dir", return_value=tmp_path / ".adk"):
        load_env_file(workspace_dir=str(tmp_path))  # should not raise
