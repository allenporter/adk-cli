"""Skill discovery and loading for adk-cli.

Skills are located in common workspace directories following the pattern:
  <workspace-root>/{.agent,.agents,_agent,_agents}/skills/<skill-name>/SKILL.md

Each SKILL.md must have YAML frontmatter with at minimum `name` and
`description` fields, followed by the skill's markdown instructions.
"""

from __future__ import annotations

import logging
import importlib.resources
from pathlib import Path
from typing import Optional

import yaml
from google.adk.skills import Frontmatter, Resources, Skill

from adk_cli.projects import find_project_root

logger = logging.getLogger(__name__)

# Workspace directory names to search for skills.
SKILL_DIRS = [".agent", ".agents", ".gemini", ".claude", ".adk"]


def _load_skill_from_content(content: str, source: str) -> Optional[Skill]:
    """Load a single skill from content string.

    Args:
        content: The content of the SKILL.md file.
        source: A description of the source for logging (e.g., path).

    Returns:
        A Skill object if the content is valid, or None if it cannot be parsed.
    """
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
                logger.warning("Could not parse frontmatter in %s: %s", source, e)
                return None

    name = frontmatter_data.get("name")
    description = frontmatter_data.get("description")

    if not name or not description:
        logger.warning(
            "Skill at %s is missing required 'name' or 'description' in frontmatter",
            source,
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

    return _load_skill_from_content(content, str(skill_md_path))


def discover_skills(
    cwd: Optional[Path] = None, *, include_builtin: bool = True
) -> list[Skill]:
    """Discover all skills from workspace directories at or above cwd.

    Searches for skills in common workspace directories (e.g. .agents/skills/).
    It checks:
    1. The current working directory (cwd)
    2. The project root (detected via find_project_root)
    3. Every directory between cwd and project root.

    Args:
        cwd: The starting directory. Defaults to current working directory.
        include_builtin: Whether to include built-in skills.

    Returns:
        List of loaded Skill objects, deduplicated by skill name.
    """
    if cwd is None:
        cwd = Path.cwd()

    cwd = cwd.resolve()
    root = find_project_root(cwd)

    seen_names: set[str] = set()
    skills: list[Skill] = []

    # Collect unique directories to search (from cwd up to root)
    search_dirs: list[Path] = []
    current = cwd
    while True:
        search_dirs.append(current)
        if current == root or current.parent == current:
            break
        current = current.parent

    # Search each candidate directory for skill folders or standalone SKILL.md files
    for search_dir in search_dirs:
        for skill_dir_name in SKILL_DIRS:
            # Pattern A: <search_dir>/<marker>/skills/<name>/SKILL.md (The "ADK" standard)
            skills_root = search_dir / skill_dir_name / "skills"
            if skills_root.is_dir():
                for skill_folder in sorted(skills_root.iterdir()):
                    if not skill_folder.is_dir():
                        continue
                    skill_md = skill_folder / "SKILL.md"
                    if skill_md.is_file():
                        skill = load_skill_from_dir(skill_md)
                        if skill and skill.name not in seen_names:
                            seen_names.add(skill.name)
                            skills.append(skill)
                            logger.debug(
                                "Loaded skill '%s' from %s", skill.name, skill_md
                            )

            # Pattern B: <search_dir>/<marker>/<name>.md (Common vendor standard)
            # This allows .agents/my-skill.md to be discovered as a skill.
            marker_root = search_dir / skill_dir_name
            if marker_root.is_dir():
                for skill_file in sorted(marker_root.glob("*.md")):
                    # Avoid reading top-level instruction files as skills here
                    if skill_file.name in {"AGENTS.md", "GEMINI.md", "CLAUDE.md"}:
                        continue
                    skill = load_skill_from_dir(skill_file)
                    if skill and skill.name not in seen_names:
                        seen_names.add(skill.name)
                        skills.append(skill)
                        logger.debug(
                            "Loaded skill '%s' from %s", skill.name, skill_file
                        )

    # Search for built-in skills
    if include_builtin:
        try:
            builtin_skills_path = importlib.resources.files("adk_cli.skills.builtin")
            for skill_folder_path in sorted(builtin_skills_path.iterdir()):
                if not skill_folder_path.is_dir():
                    continue
                skill_md_path = skill_folder_path / "SKILL.md"
                if not skill_md_path.is_file():
                    continue

                content = skill_md_path.read_text(encoding="utf-8")
                skill = _load_skill_from_content(content, str(skill_md_path))

                if skill is None:
                    continue
                if skill.name in seen_names:
                    logger.debug(
                        "Skipping duplicate built-in skill '%s' from %s",
                        skill.name,
                        skill_md_path,
                    )
                    continue
                seen_names.add(skill.name)
                skills.append(skill)
                logger.debug(
                    "Loaded built-in skill '%s' from %s", skill.name, skill_md_path
                )
        except (ImportError, FileNotFoundError) as e:
            logger.warning("Could not load built-in skills: %s", e)

    return skills
