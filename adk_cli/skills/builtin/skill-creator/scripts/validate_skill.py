#!/usr/bin/env python3

"""
Quick validation logic for skills.
"""

import os
import sys
import re
from pathlib import Path


def validate_skill(skill_path):
    skill_path_obj = Path(skill_path)

    if not skill_path_obj.exists() or not skill_path_obj.is_dir():
        return {"valid": False, "message": f"Path is not a directory: {skill_path}"}

    skill_md_path = skill_path_obj / "SKILL.md"
    if not skill_md_path.exists():
        return {"valid": False, "message": "SKILL.md not found"}

    try:
        with open(skill_md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as err:
        return {"valid": False, "message": f"Error reading SKILL.md: {err}"}

    if not content.startswith("---"):
        return {"valid": False, "message": "No YAML frontmatter found"}

    parts = content.split("---")
    if len(parts) < 3:
        return {"valid": False, "message": "Invalid frontmatter format"}

    frontmatter_text = parts[1]

    name_match = re.search(r"^name:\s*(.+)$", frontmatter_text, re.MULTILINE)
    # Match description: "text" or description: 'text' or description: text
    desc_match = re.search(
        r'^description:\s*(?:\'([^\']*)\'|"([^"]*)"|(.+))$',
        frontmatter_text,
        re.MULTILINE,
    )

    if not name_match:
        return {"valid": False, "message": 'Missing "name" in frontmatter'}
    if not desc_match:
        return {
            "valid": False,
            "message": "Description must be a single-line string: description: ...",
        }

    name = name_match.group(1).strip()
    description = (
        desc_match.group(1)
        if desc_match.group(1) is not None
        else desc_match.group(2)
        if desc_match.group(2) is not None
        else desc_match.group(3) or ""
    ).strip()

    if "\n" in description:
        return {
            "valid": False,
            "message": "Description must be a single line (no newlines)",
        }

    if not re.match(r"^[a-z0-9-]+$", name):
        return {"valid": False, "message": f"Name '{name}' should be hyphen-case"}

    if len(description) > 1024:
        return {"valid": False, "message": "Description is too long (max 1024)"}

    # Check for TODOs
    for root, dirs, files in os.walk(skill_path_obj):
        # Exclude directories
        dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "__pycache__"]]
        for file in files:
            file_path = Path(root) / file
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    file_content = f.read()
                    if "TODO:" in file_content:
                        return {
                            "valid": True,
                            "message": "Skill has unresolved TODOs",
                            "warning": f"Found unresolved TODO in {file_path.relative_to(skill_path_obj)}",
                        }
            except Exception:
                # Skip files that can't be read as text
                continue

    return {"valid": True, "message": "Skill is valid!"}


if __name__ == "__main__":
    if len(sys.argv) != 1:
        # If run directly as a script (not imported), we might want to pass path
        # But this logic wasn't fully developed in the Node.js version same way
        # Actually it was in Node version.
        pass

    if len(sys.argv) < 2:
        print("Usage: python3 validate_skill.py <skill_directory>")
        sys.exit(1)

    skill_dir_arg = sys.argv[1]
    if ".." in skill_dir_arg:
        print("❌ Error: Path traversal detected in skill directory path.")
        sys.exit(1)

    result = validate_skill(os.path.abspath(skill_dir_arg))
    if "warning" in result:
        print(f"⚠️  {result['warning']}")
    if result["valid"]:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ {result['message']}")
        sys.exit(1)
