#!/usr/bin/env python3

"""
Skill Packager - Creates a distributable .skill file of a skill folder
"""

import os
import sys
import zipfile
from pathlib import Path
from validate_skill import validate_skill


def main():
    if len(sys.argv) < 2:
        print(
            "Usage: python3 package_skill.py <path/to/skill-folder> [output-directory]"
        )
        sys.exit(1)

    skill_path_arg = sys.argv[1]
    output_dir_arg = sys.argv[2] if len(sys.argv) > 2 else os.getcwd()

    if ".." in skill_path_arg or ".." in output_dir_arg:
        print("❌ Error: Path traversal detected in arguments.")
        sys.exit(1)

    skill_path = Path(skill_path_arg).resolve()
    output_dir = Path(output_dir_arg).resolve()
    skill_name = skill_path.name

    # 1. Validate first
    print("🔍 Validating skill...")
    result = validate_skill(str(skill_path))
    if not result["valid"]:
        print(f"❌ Validation failed: {result['message']}")
        sys.exit(1)

    if result.get("warning"):
        print(f"⚠️  {result['warning']}")
        print("Please resolve all TODOs before packaging.")
        sys.exit(1)
    print("✅ Skill is valid!")

    # 2. Package
    output_filename = output_dir / f"{skill_name}.skill"

    try:
        with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(skill_path):
                # Exclude junk directories/files
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in [".git", "__pycache__", ".DS_Store", "node_modules"]
                ]
                files = [f for f in files if f not in [".DS_Store", "Thumbs.db"]]

                for file in files:
                    file_path = Path(root) / file
                    # Calculate arcname (relative path inside zip)
                    arcname = file_path.relative_to(skill_path)
                    zipf.write(file_path, arcname)

        print(f"✅ Successfully packaged skill to: {output_filename}")
    except Exception as err:
        print(f"❌ Error packaging: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
