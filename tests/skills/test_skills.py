"""Tests for adk_cli.skills module."""

from pathlib import Path
from textwrap import dedent

import pytest

from adk_cli.skills import discover_skills, load_skill_from_dir


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_skill(
    parent: Path, skill_name: str, *, dir_name: str = ".agent", extra: str = ""
) -> Path:
    """Create a SKILL.md at the standard path under parent."""
    folder = parent / dir_name / "skills" / skill_name
    folder.mkdir(parents=True, exist_ok=True)
    skill_md = folder / "SKILL.md"
    skill_md.write_text(
        dedent(f"""\
            ---
            name: {skill_name}
            description: Description of {skill_name}.
            {extra}
            ---

            # {skill_name} Skill

            Some instructions here.
        """),
        encoding="utf-8",
    )
    return skill_md


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A temp dir that acts as a workspace root (has .git)."""
    (tmp_path / ".git").mkdir()
    return tmp_path


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------


def test_load_skill_valid(workspace: Path) -> None:
    """load_skill_from_dir returns a Skill with correct name, description, and instructions."""
    skill_md = _make_skill(workspace, "my-skill")
    skill = load_skill_from_dir(skill_md)

    assert skill is not None
    assert skill.name == "my-skill"
    assert skill.description == "Description of my-skill."
    assert "Some instructions here." in skill.instructions


def test_load_skill_missing_name_returns_none(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\ndescription: Missing name.\n---\nBody.", encoding="utf-8")
    assert load_skill_from_dir(skill_md) is None


def test_load_skill_missing_description_returns_none(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\nname: no-desc\n---\nBody.", encoding="utf-8")
    assert load_skill_from_dir(skill_md) is None


def test_load_skill_invalid_yaml_returns_none(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("---\n: bad: yaml: [\n---\nBody.", encoding="utf-8")
    assert load_skill_from_dir(skill_md) is None


def test_load_skill_missing_file_returns_none(tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist" / "SKILL.md"
    assert load_skill_from_dir(missing) is None


def test_load_skill_no_frontmatter_returns_none(tmp_path: Path) -> None:
    """A file without --- delimiters has no name/description, so returns None."""
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text("Just some markdown without frontmatter.", encoding="utf-8")
    assert load_skill_from_dir(skill_md) is None


def test_load_skill_optional_fields(tmp_path: Path) -> None:
    skill_md = tmp_path / "SKILL.md"
    skill_md.write_text(
        dedent("""\
            ---
            name: full-skill
            description: A full skill.
            license: Apache-2.0
            compatibility: ">=1.0"
            allowed_tools: "read_file, write_file"
            ---
            Body.
        """),
        encoding="utf-8",
    )
    skill = load_skill_from_dir(skill_md)
    assert skill is not None
    assert skill.frontmatter.license == "Apache-2.0"
    assert skill.frontmatter.compatibility == ">=1.0"
    assert skill.frontmatter.allowed_tools == "read_file, write_file"


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


def test_discover_skills_finds_skill_in_agent_dir(workspace: Path) -> None:
    _make_skill(workspace, "developer")
    skills = discover_skills(workspace, include_builtin=False)
    assert len(skills) == 1
    assert skills[0].name == "developer"


def test_discover_skills_all_four_dir_patterns(workspace: Path) -> None:
    dir_names = [".agent", ".agents", ".gemini", ".claude"]
    for i, dir_name in enumerate(dir_names):
        _make_skill(workspace, f"skill-{i}", dir_name=dir_name)
    skills = discover_skills(workspace, include_builtin=False)
    assert len(skills) == 4


def test_discover_skills_deduplicates_by_name(workspace: Path) -> None:
    for dir_name in [".agent", ".agents"]:
        _make_skill(workspace, "duplicate", dir_name=dir_name)
    skills = discover_skills(workspace, include_builtin=False)
    assert len(skills) == 1


def test_discover_skills_finds_skills_in_ancestors(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / ".git").mkdir()
    _make_skill(root, "root-skill")

    subdir = root / "subdir"
    subdir.mkdir()
    _make_skill(subdir, "sub-skill")

    skills = discover_skills(subdir, include_builtin=False)
    names = {s.name for s in skills}
    assert "sub-skill" in names
    assert "root-skill" in names


def test_discover_skills_stops_at_git_root(tmp_path: Path) -> None:
    grandparent = tmp_path / "grandparent"
    grandparent.mkdir()
    _make_skill(grandparent, "grandparent-skill")

    parent = grandparent / "nested"
    parent.mkdir()
    (parent / ".git").mkdir()
    _make_skill(parent, "parent-skill")

    cwd = parent / "src"
    cwd.mkdir()

    skills = discover_skills(cwd, include_builtin=False)
    names = {s.name for s in skills}
    assert "parent-skill" in names
    assert "grandparent-skill" not in names


def test_discover_skills_empty_skills_dir(workspace: Path) -> None:
    (workspace / ".agent" / "skills").mkdir(parents=True)
    assert discover_skills(workspace, include_builtin=False) == []


def test_discover_skills_no_skill_dirs(workspace: Path) -> None:
    assert discover_skills(workspace, include_builtin=False) == []


def test_discover_skills_defaults_to_cwd(
    monkeypatch: pytest.MonkeyPatch, workspace: Path
) -> None:
    _make_skill(workspace, "cwd-skill")
    monkeypatch.chdir(workspace)
    skills = discover_skills()
    assert any(s.name == "cwd-skill" for s in skills)


def test_discover_skills_finds_builtin_skill() -> None:
    skills = discover_skills()
    # skill-creator is a builtin skill
    assert any(s.name == "skill-creator" for s in skills)
