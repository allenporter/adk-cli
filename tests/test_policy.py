import pytest
from adk_cli.policy import CustomPolicyEngine, SecurityPlugin, PermissionMode
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


@pytest.mark.asyncio
async def test_policy_auto_mode(
    mock_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.AUTO)
    plugin = SecurityPlugin(engine)

    result = await plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is None  # None means ALLOW


@pytest.mark.asyncio
async def test_policy_ask_mode_sensitive(
    mock_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    plugin = SecurityPlugin(engine)

    result = await plugin.before_tool_callback(
        tool=mock_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is not None
    assert "Confirmation required" in result["error"]
    # Check if request_confirmation was called on tool_context
    mock_tool_context.request_confirmation.assert_called_once()


@pytest.mark.asyncio
async def test_policy_ask_mode_read_only(
    mock_read_tool: MagicMock, mock_tool_context: MagicMock
) -> None:
    engine = CustomPolicyEngine(mode=PermissionMode.ASK)
    plugin = SecurityPlugin(engine)

    result = await plugin.before_tool_callback(
        tool=mock_read_tool, tool_args={}, tool_context=mock_tool_context
    )

    assert result is None  # Read-only tools should be allowed


@pytest.mark.asyncio
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
