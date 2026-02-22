from click.testing import CliRunner
from adk_cli.main import cli
from unittest.mock import patch, AsyncMock
from google.adk.events.event import Event
from google.genai import types


_MOCK_API_KEY = "test-api-key-abc123"


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "adk-cli" in result.output
    assert "agents" in result.output
    assert "mcp" in result.output


def test_cli_agents() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["agents"])
    assert result.exit_code == 0
    assert "Listing agents and skills..." in result.output


def test_cli_mcp() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp"])
    assert result.exit_code == 0
    assert "Managing MCP connections..." in result.output


def test_cli_no_api_key_exits_with_instructions() -> None:
    """When no API key is found, should print helpful instructions and exit."""
    runner = CliRunner()
    with patch("adk_cli.main._resolve_api_key", return_value=None):
        result = runner.invoke(cli, ["chat", "Hello"])
    assert result.exit_code == 1
    assert "aistudio.google.com" in result.output


def test_cli_chat_direct() -> None:
    runner = CliRunner()
    with (
        patch("adk_cli.main._build_runner_or_exit") as mock_build,
        patch("adk_cli.main.AdkTuiApp") as mock_tui,
    ):
        mock_build.return_value = mock_build  # just needs to be truthy
        mock_instance = mock_tui.return_value
        result = runner.invoke(cli, ["chat", "Hello world"])
        assert result.exit_code == 0
        mock_tui.assert_called_once()
        mock_instance.run.assert_called_once()


def test_cli_chat_print() -> None:
    runner = CliRunner()
    with patch("adk_cli.main._build_runner_or_exit") as mock_build:
        mock_runner = mock_build.return_value
        fake_event = Event(
            author="model",
            content=types.Content(parts=[types.Part(text="Mocked response")]),
        )
        mock_runner.run.return_value = [fake_event]

        result = runner.invoke(cli, ["chat", "-p", "Hello world"])
        assert result.exit_code == 0
        assert "Executing one-off query" in result.output
        assert "Project:" in result.output
        assert "Session:" in result.output
        assert "Mocked response" in result.output


def test_cli_no_args_shows_tui() -> None:
    runner = CliRunner()
    with (
        patch("adk_cli.main._build_runner_or_exit") as mock_build,
        patch("adk_cli.main.AdkTuiApp") as mock_tui,
    ):
        mock_build.return_value = mock_build
        mock_instance = mock_tui.return_value
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        mock_tui.assert_called_once()
        mock_instance.run.assert_called_once()


def test_cli_sessions_list() -> None:
    runner = CliRunner()
    with patch("adk_cli.main.SqliteSessionService") as mock_service:
        mock_instance = mock_service.return_value
        mock_instance.list_sessions = AsyncMock()
        mock_instance.list_sessions.return_value.sessions = []

        result = runner.invoke(cli, ["sessions", "list"])
        assert result.exit_code == 0
        assert "No sessions found." in result.output
