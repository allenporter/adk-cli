import pytest
from adk_cli.policy import CustomPolicyEngine, PermissionMode, PolicyOutcome


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
