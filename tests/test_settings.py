"""Tests for adk_cli.settings module."""

import json
from pathlib import Path
from unittest.mock import patch

from adk_cli.settings import (
    load_settings,
    save_settings,
    get_global_settings_path,
    get_global_adk_dir,
)


def test_get_global_adk_dir_under_home(tmp_path: Path) -> None:
    with patch("adk_cli.settings.os.path.expanduser", return_value=str(tmp_path)):
        result = get_global_adk_dir()
    assert result == tmp_path / ".adk"


def test_get_global_settings_path(tmp_path: Path) -> None:
    with patch("adk_cli.settings.os.path.expanduser", return_value=str(tmp_path)):
        result = get_global_settings_path()
    assert result == tmp_path / ".adk" / "settings.json"


def test_load_settings_returns_empty_dict_when_file_missing(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"
    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_settings()
    assert result == {}


def test_load_settings_reads_existing_file(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text(json.dumps({"api_key": "test-key-123"}))

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_settings()

    assert result == {"api_key": "test-key-123"}


def test_load_settings_returns_empty_dict_on_corrupt_json(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text("{not valid json")

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        result = load_settings()

    assert result == {}


def test_save_settings_creates_directory_and_file(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        save_settings({"api_key": "saved-key"})

    assert settings_path.exists()
    data = json.loads(settings_path.read_text())
    assert data == {"api_key": "saved-key"}


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    settings_path = tmp_path / ".adk" / "settings.json"
    original = {"api_key": "round-trip-key", "other": "value"}

    with patch("adk_cli.settings.get_global_settings_path", return_value=settings_path):
        save_settings(original)
        loaded = load_settings()

    assert loaded == original
