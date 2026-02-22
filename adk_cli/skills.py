"""Skill discovery and loading for adk-cli.

Skills are located in common workspace directories following the pattern:
  <workspace-root>/{.agent,.agents,_agent,_agents}/skills/<skill-name>/SKILL.md

Each SKILL.md must have YAML frontmatter with at minimum `name` and
`description` fields, followed by the skill's markdown instructions.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml
from google.adk.skills import Frontmatter, Resources, Skill

logger = logging.getLogger(__name__)

# Workspace directory names to search for skills.
SKILL_DIRS = [".agent", ".agents", ".gemini", ".claude"]

# Files that indicate a workspace root (stop searching upward past this).
_WORKSPACE_ROOT_MARKERS = [".git", "pyproject.toml", "package.json", "setup.py"]


# TODO: Remove this once google-adk provides `load_skill_from_dir` natively (added in google/adk-python@223d9a7)
def load_skill_from_dir(skill_md_path: Path) -> Optional[Skill]:
    """Load a single skill from a SKILL.md file.

    Args:
        skill_md_path: Absolute path to a SKILL.md file.

    Returns:
        A Skill object if the file is valid, or None if it cannot be parsed.
    """
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Could not read skill file %s: %s", skill_md_path, e)
        return None

    # Parse YAML frontmatter between --- delimiters.
    frontmatter_data: dict = {}
    instructions = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                frontmatter_data = yaml.safe_load(parts[1]) or {}
                instructions = parts[2].strip()
            except yaml.YAMLError as e:
                logger.warning(
                    "Could not parse frontmatter in %s: %s", skill_md_path, e
                )
                return None

    name = frontmatter_data.get("name")
    description = frontmatter_data.get("description")

    if not name or not description:
        logger.warning(
            "Skill at %s is missing required 'name' or 'description' in frontmatter",
            skill_md_path,
        )
        return None

    frontmatter = Frontmatter(
        name=str(name),
        description=str(description),
        license=frontmatter_data.get("license"),
        compatibility=frontmatter_data.get("compatibility"),
        allowed_tools=frontmatter_data.get("allowed_tools"),
        metadata={
            k: str(v)
            for k, v in frontmatter_data.items()
            if k
            not in {"name", "description", "license", "compatibility", "allowed_tools"}
        },
    )

    return Skill(
        frontmatter=frontmatter, instructions=instructions, resources=Resources()
    )


def discover_skills(
    cwd: Optional[Path] = None, *, include_builtin: bool = True
) -> list[Skill]:
    """Discover all skills from workspace directories at or above cwd.

    Searches each ancestor directory (starting from cwd) for skill files
    matching the pattern: <dir>/skills/*/SKILL.md in any of the common
    workspace directories. Stops searching upward once a workspace root
    marker (e.g. .git, pyproject.toml) is found.

    Args:
        cwd: The starting directory. Defaults to the current working directory.
        include_builtin: Whether to include built-in skills.

    Returns:
        List of loaded Skill objects, deduplicated by skill name (first found wins).
    """
    if cwd is None:
        cwd = Path.cwd()

    cwd = cwd.resolve()
    seen_names: set[str] = set()
    skills: list[Skill] = []

    # Walk upward, collecting skill directories.
    search_dirs: list[Path] = []
    current = cwd
    while True:
        search_dirs.append(current)
        # Stop if we've hit a workspace root.
        for marker in _WORKSPACE_ROOT_MARKERS:
            if (current / marker).exists():
                # Found a root marker — include this dir but go no further.
                current = None
                break
        if current is None:
            break
        parent = current.parent
        if parent == current:
            # Reached filesystem root.
            break
        current = parent

    # Search each candidate directory for SKILL.md files.
    for search_dir in search_dirs:
        for skill_dir_name in SKILL_DIRS:
            skills_root = search_dir / skill_dir_name / "skills"
            if not skills_root.is_dir():
                continue
            # Each subdirectory of skills_root is a named skill.
            for skill_folder in sorted(skills_root.iterdir()):
                if not skill_folder.is_dir():
                    continue
                skill_md = skill_folder / "SKILL.md"
                if not skill_md.is_file():
                    continue
                skill = load_skill_from_dir(skill_md)
                if skill is None:
                    continue
                if skill.name in seen_names:
                    logger.debug(
                        "Skipping duplicate skill '%s' from %s", skill.name, skill_md
                    )
                    continue
                seen_names.add(skill.name)
                skills.append(skill)
                logger.debug("Loaded skill '%s' from %s", skill.name, skill_md)

    # Search for built-in skills packaged with adk-cli.
    if include_builtin:
        builtin_dir = Path(__file__).parent / "skills" / "builtin"
        if builtin_dir.is_dir():
            for skill_folder in sorted(builtin_dir.iterdir()):
                if not skill_folder.is_dir():
                    continue
                skill_md = skill_folder / "SKILL.md"
                if not skill_md.is_file():
                    continue
                skill = load_skill_from_dir(skill_md)
                if skill is None:
                    continue
                if skill.name in seen_names:
                    logger.debug(
                        "Skipping duplicate built-in skill '%s' from %s",
                        skill.name,
                        skill_md,
                    )
                    continue
                seen_names.add(skill.name)
                skills.append(skill)
                logger.debug("Loaded built-in skill '%s' from %s", skill.name, skill_md)

    return skills
