"""Tests for built-in skill agents."""

from pathlib import Path
import pytest
from adk_cli.tools import _get_agent_metadata


def test_builtin_skill_exists():
    """Verify the feature-dev skill exists in the builtin directory."""
    skill_path = (
        Path(__file__).parent.parent
        / "adk_cli"
        / "skills"
        / "builtin"
        / "feature-dev"
        / "SKILL.md"
    )
    assert skill_path.is_file(), f"Built-in skill not found at {skill_path}"

    # Check if it has the name defined
    content = skill_path.read_text(encoding="utf-8")
    assert "name: feature-dev" in content


@pytest.mark.parametrize(
    "agent_name", ["code-explorer", "code-architect", "code-reviewer"]
)
def test_parsing_builtin_agents(agent_name):
    """Verify that each built-in agent markdown file exists and has correct metadata."""
    metadata = _get_agent_metadata(agent_name)

    # Verify metadata was actually loaded (not just returning {} or fallback)
    assert metadata, f"Metadata for {agent_name} should not be empty"
    assert "instruction" in metadata, f"Agent {agent_name} should have an instruction"

    # Verify mandatory fields from our YAML frontmatter standard
    assert metadata.get("name") == agent_name, (
        f"Agent name in YAML should match {agent_name}"
    )
    assert isinstance(metadata.get("allowed_tools"), list), (
        f"Agent {agent_name} must specify allowed_tools"
    )
    assert len(metadata["allowed_tools"]) > 0, (
        f"Agent {agent_name} should have at least one tool"
    )
    assert len(metadata["instruction"]) > 10, (
        f"Agent {agent_name} has a suspicious empty instruction"
    )

    # Make sure we didn't duplicate any tools
    assert len(metadata["allowed_tools"]) == len(set(metadata["allowed_tools"])), (
        f"Found duplicate tools in {agent_name}"
    )


def test_metadata_loader_fallback():
    """Verify _get_agent_metadata returns {} for non-existent agents."""
    metadata = _get_agent_metadata("non-existent-agent-12345")
    assert metadata == {}
