"""Tests for agent_factory module: build_runner() and build_adk_agent()."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from adk_coder.agent_factory import build_adk_agent, build_runner
from adk_coder.policy import PermissionMode


@patch("adk_coder.agent_factory.get_session_db_path", return_value="/tmp/test.db")
@patch("adk_coder.agent_factory.SqliteSessionService")
@patch("adk_coder.agent_factory.Runner")
@patch("adk_coder.agent_factory.App")
@patch("adk_coder.agent_factory.SecurityPlugin")
@patch("adk_coder.agent_factory.CustomPolicyEngine")
@patch("adk_coder.agent_factory.find_project_root")
@patch("adk_coder.agent_factory.load_settings", return_value={})
@patch("adk_coder.agent_factory.build_adk_agent")
def test_build_runner_returns_runner(
    mock_build_agent: MagicMock,
    mock_settings: MagicMock,
    mock_root: MagicMock,
    mock_policy: MagicMock,
    mock_sec: MagicMock,
    mock_app: MagicMock,
    mock_runner: MagicMock,
    mock_session: MagicMock,
    mock_db_path: MagicMock,
) -> None:
    """build_runner() should assemble and return a Runner with expected config."""
    mock_agent = MagicMock(name="fake_agent")
    mock_build_agent.return_value = mock_agent

    runner = build_runner()

    # Verify Runner was constructed
    mock_runner.assert_called_once()
    call_kwargs = mock_runner.call_args[1]
    assert call_kwargs["auto_create_session"] is True
    assert runner == mock_runner.return_value

    # Verify App was constructed with the agent and security plugin
    mock_app.assert_called_once()
    app_kwargs = mock_app.call_args[1]
    assert app_kwargs["root_agent"] == mock_agent
    assert mock_sec.return_value in app_kwargs["plugins"]


@patch("adk_coder.agent_factory.get_session_db_path", return_value="/tmp/test.db")
@patch("adk_coder.agent_factory.SqliteSessionService")
@patch("adk_coder.agent_factory.Runner")
@patch("adk_coder.agent_factory.App")
@patch("adk_coder.agent_factory.SecurityPlugin")
@patch("adk_coder.agent_factory.CustomPolicyEngine")
@patch("adk_coder.agent_factory.find_project_root")
@patch("adk_coder.agent_factory.load_settings", return_value={})
@patch("adk_coder.agent_factory.build_adk_agent")
def test_build_runner_passes_model_through(
    mock_build_agent: MagicMock,
    mock_settings: MagicMock,
    mock_root: MagicMock,
    mock_policy: MagicMock,
    mock_sec: MagicMock,
    mock_app: MagicMock,
    mock_runner: MagicMock,
    mock_session: MagicMock,
    mock_db_path: MagicMock,
) -> None:
    """build_runner(model=...) should forward the model to build_adk_agent()."""
    build_runner(model="gemini-2.0-flash")

    mock_build_agent.assert_called_once_with(
        model="gemini-2.0-flash",
        instruction=None,
        tool_names=None,
        include_skills=True,
        agent_name="adk_coder_agent",
        workspace_path=None,
        extra_tools=None,
    )


@patch("adk_coder.agent_factory.get_session_db_path", return_value="/tmp/test.db")
@patch("adk_coder.agent_factory.SqliteSessionService")
@patch("adk_coder.agent_factory.Runner")
@patch("adk_coder.agent_factory.App")
@patch("adk_coder.agent_factory.SecurityPlugin")
@patch("adk_coder.agent_factory.CustomPolicyEngine")
@patch("adk_coder.agent_factory.find_project_root")
@patch("adk_coder.agent_factory.load_settings", return_value={})
@patch("adk_coder.agent_factory.build_adk_agent")
def test_build_runner_uses_permission_mode(
    mock_build_agent: MagicMock,
    mock_settings: MagicMock,
    mock_root: MagicMock,
    mock_policy: MagicMock,
    mock_sec: MagicMock,
    mock_app: MagicMock,
    mock_runner: MagicMock,
    mock_session: MagicMock,
    mock_db_path: MagicMock,
) -> None:
    """build_runner(permission_mode=...) should create a matching CustomPolicyEngine."""
    build_runner(permission_mode="auto")

    mock_policy.assert_called_once()
    call_kwargs = mock_policy.call_args[1]
    assert call_kwargs["mode"] == PermissionMode("auto")


@patch("adk_coder.agent_factory.get_session_db_path", return_value="/tmp/test.db")
@patch("adk_coder.agent_factory.SqliteSessionService")
@patch("adk_coder.agent_factory.Runner")
@patch("adk_coder.agent_factory.App")
@patch("adk_coder.agent_factory.SecurityPlugin")
@patch("adk_coder.agent_factory.CustomPolicyEngine")
@patch("adk_coder.agent_factory.find_project_root")
@patch("adk_coder.agent_factory.load_settings", return_value={})
@patch("adk_coder.agent_factory.build_adk_agent")
def test_build_runner_passes_workspace_path(
    mock_build_agent: MagicMock,
    mock_settings: MagicMock,
    mock_root: MagicMock,
    mock_policy: MagicMock,
    mock_sec: MagicMock,
    mock_app: MagicMock,
    mock_runner: MagicMock,
    mock_session: MagicMock,
    mock_db_path: MagicMock,
) -> None:
    """build_runner(workspace_path=...) should forward it to build_adk_agent() and find_project_root()."""
    ws = Path("/srv/workspaces/my-project")

    build_runner(workspace_path=ws)

    mock_build_agent.assert_called_once_with(
        model=None,
        instruction=None,
        tool_names=None,
        include_skills=True,
        agent_name="adk_coder_agent",
        workspace_path=ws,
        extra_tools=None,
    )


@patch("adk_coder.agent_factory.LlmAgent")
@patch("adk_coder.agent_factory.BuiltInPlanner")
@patch("adk_coder.agent_factory.AdkRetryGemini")
@patch("adk_coder.agent_factory.get_essential_tools", return_value=[])
@patch("adk_coder.agent_factory.discover_skills", return_value=[])
@patch(
    "adk_coder.agent_factory.load_settings",
    return_value={"default_model": "test-model"},
)
@patch("adk_coder.agent_factory.find_project_root")
def test_build_adk_agent_passes_workspace_path(
    mock_root: MagicMock,
    mock_settings: MagicMock,
    mock_skills: MagicMock,
    mock_tools: MagicMock,
    mock_retry: MagicMock,
    mock_planner: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """build_adk_agent(workspace_path=...) should forward it to find_project_root() and discover_skills()."""
    ws = Path("/srv/workspaces/my-project")
    mock_root.return_value = ws

    build_adk_agent(workspace_path=ws)

    mock_root.assert_called_once_with(ws)
    mock_skills.assert_called_once_with(ws)
