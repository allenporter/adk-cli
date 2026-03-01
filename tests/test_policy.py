import pytest
from adk_cli.policy import (
    CustomPolicyEngine,
    SecurityPlugin,
    PermissionMode,
    PolicyOutcome,
)
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext
from google.adk.events.event_actions import EventActions
from google.adk.tools.tool_confirmation import ToolConfirmation
from unittest.mock import MagicMock


@pytest.fixture
def mock_tool() -> MagicMock:
    tool = MagicMock(spec=BaseTool)
    tool.name = "rm"
    return tool


@pytest.fixture
def mock_read_tool() -> MagicMock:
    tool = MagicMock(spec=BaseTool)
    tool.name = "ls"
    return tool


@pytest.fixture
def mock_tool_context() -> MagicMock:
    # Helper to create a ToolContext-like object with necessary attributes
    ctx = MagicMock(spec=ToolContext)
    ctx.tool_confirmation = None
    ctx.event_actions = MagicMock(spec=EventActions)
    # requested_tool_confirmations is a dict in EventActions
    ctx.event_actions.requested_tool_confirmations = {}
    return ctx


async def test_policy_auto_mode(
    mock_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.AUTO)
    plugin = SecurityPlugin(engine)

    result = await plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is None  # None means ALLOW


async def test_policy_ask_mode_sensitive(
    mock_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    plugin = SecurityPlugin(engine)

    result = await plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is not None
    assert "User denied execution" in result["error"]
    # Check if request_confirmation was called on tool_context
    mock_tool_context.request_confirmation.assert_called_once()


async def test_policy_ask_mode_read_only(
    mock_read_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    plugin = SecurityPlugin(engine)

    result = await plugin.before_tool_callback(
        tool=mock_read_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is None  # Read-only tools should be allowed


async def test_policy_already_confirmed(
    mock_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    plugin = SecurityPlugin(engine)

    # Simulate already confirmed
    mock_tool_context.tool_confirmation = MagicMock(spec=ToolConfirmation)
    mock_tool_context.tool_confirmation.confirmed = True

    result = await plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is None  # Should be allowed if already confirmed


async def test_policy_safe_bash_command(mock_tool_context: MagicMock) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    plugin = SecurityPlugin(engine)

    mock_bash_tool = MagicMock(spec=BaseTool)
    mock_bash_tool.name = "bash"

    # Test a safe command
    result = await plugin.before_tool_callback(
        tool=mock_bash_tool,
        tool_args={"command": "git status"},
        tool_context=mock_tool_context,
    )
    assert result is None

    # Test an unsafe command
    result = await plugin.before_tool_callback(
        tool=mock_bash_tool,
        tool_args={"command": "rm -rf /"},
        tool_context=mock_tool_context,
    )
    assert result is not None
    assert "User denied execution" in result["error"]


@pytest.mark.asyncio
async def test_session_granular_permission_bash():
    """Test that granular 'bash' permissions work correctly across calls."""
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)

    # Initially, it should require confirmation
    res1 = await engine.evaluate("bash", {"command": "ls -la"})
    assert res1.outcome == PolicyOutcome.CONFIRM

    # Allow for session
    engine.allow_for_session("bash", {"command": "ls -la"})

    # Now same command should be allowed
    res2 = await engine.evaluate("bash", {"command": "ls -la"})
    assert res2.outcome == PolicyOutcome.ALLOW

    # Different command should still require confirmation (provided it's not in SAFE_BASH_COMMANDS)
    res3 = await engine.evaluate("bash", {"command": "rm -rf /"})
    assert res3.outcome == PolicyOutcome.CONFIRM


@pytest.mark.asyncio
async def test_session_granular_permission_files():
    """Test that granular file-based permissions work for edit/write/cat."""
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    file_path = "src/main.py"

    # Initially, it should require confirmation
    res1 = await engine.evaluate("write_file", {"path": file_path, "content": "hello"})
    assert res1.outcome == PolicyOutcome.CONFIRM

    # Allow for session
    engine.allow_for_session("write_file", {"path": file_path})

    # Same path should be allowed
    res2 = await engine.evaluate("write_file", {"path": file_path, "content": "world"})
    assert res2.outcome == PolicyOutcome.ALLOW

    # Other file-based tools for the SAME path should be allowed (since they share the logic)
    # Note: Currently they use separate keys in the set, so we need to verify if that's desired.
    # Actually, allow_for_session uses tool_name as the key.
    res3 = await engine.evaluate("edit_file", {"path": file_path})
    assert res3.outcome == PolicyOutcome.CONFIRM  # Because it's a different tool_name

    # Allow edit_file for this path too
    engine.allow_for_session("edit_file", {"path": file_path})
    res4 = await engine.evaluate("edit_file", {"path": file_path})
    assert res4.outcome == PolicyOutcome.ALLOW

    # Different path still requires confirmation
    res5 = await engine.evaluate("write_file", {"path": "other.txt"})
    assert res5.outcome == PolicyOutcome.CONFIRM


@pytest.mark.asyncio
async def test_session_generic_permission():
    """Test that tools without granular logic fallback to tool-wide allowance."""
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    tool_name = "random_tool"

    # Initially, confirm
    res1 = await engine.evaluate(tool_name, {"arg": 1})
    assert res1.outcome == PolicyOutcome.CONFIRM

    # Allow for session (generic)
    engine.allow_for_session(tool_name, {"arg": 1})

    # Any call to this tool should now be allowed
    res2 = await engine.evaluate(tool_name, {"arg": 1})
    assert res2.outcome == PolicyOutcome.ALLOW

    res3 = await engine.evaluate(tool_name, {"arg": 2})
    assert res3.outcome == PolicyOutcome.ALLOW
