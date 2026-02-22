#!/usr/bin/env python3

"""
Skill Initializer - Creates a new skill from template

Usage:
    python3 init_skill.py <skill-name> --path <path>

Examples:
    python3 init_skill.py my-new-skill --path skills/public
"""

import os
import sys
import argparse
from pathlib import Path

SKILL_TEMPLATE = """---
name: {skill_name}
description: TODO: Complete and informative explanation of what the skill does and when to use it. Include WHEN to use this skill - specific scenarios, file types, or tasks that trigger it.
---

# {skill_title}

## Overview

[TODO: 1-2 sentences explaining what this skill enables]

## Structuring This Skill

[TODO: Choose the structure that best fits this skill's purpose. Common patterns:

**1. Workflow-Based** (best for sequential processes)
- Works well when there are clear step-by-step procedures
- Example: CSV-Processor skill with "Workflow Decision Tree" → "Ingestion" → "Cleaning" → "Analysis"
- Structure: ## Overview → ## Workflow Decision Tree → ## Step 1 → ## Step 2...

**2. Task-Based** (best for tool collections)
- Works well when the skill offers different operations/capabilities
- Example: PDF skill with "Quick Start" → "Merge PDFs" → "Split PDFs" → "Extract Text"
- Structure: ## Overview → ## Quick Start → ## Task Category 1 → ## Task Category 2...

**3. Reference/Guidelines** (best for standards or specifications)
- Works well for brand guidelines, coding standards, or requirements
- Example: Brand styling with "Brand Guidelines" → "Colors" → "Typography" → "Features"
- Structure: ## Overview → ## Guidelines → ## Specifications → ## Usage...

**4. Capabilities-Based** (best for integrated systems)
- Works well when the skill provides multiple interrelated features
- Example: Product Management with "Core Capabilities" → numbered capability list
- Structure: ## Overview → ## Core Capabilities → ### 1. Feature → ### 2. Feature...

Patterns can be mixed and matched as needed. Most skills combine patterns (e.g., start with task-based, add workflow for complex operations).

Delete this entire "Structuring This Skill" section when done - it's just guidance.]

## [TODO: Replace with the first main section based on chosen structure]

[TODO: Add content here. See examples in existing skills:
- Code samples for technical skills
- Decision trees for complex workflows
- Concrete examples with realistic user requests
- References to scripts/templates/references as needed]

## Resources

This skill includes example resource directories that demonstrate how to organize different types of bundled resources:

### scripts/
Executable code that can be run directly to perform specific operations.

**Examples from other skills:**
- PDF skill: fill_fillable_fields.py, extract_form_field_info.py - utilities for PDF manipulation
- CSV skill: normalize_schema.py, merge_datasets.py - utilities for tabular data manipulation

**Appropriate for:** Python scripts (.py), shell scripts, or any executable code that performs automation, data processing, or specific operations.

**Note:** Scripts may be executed without loading into context, but can still be read by Gemini CLI for patching or environment adjustments.

### references/
Documentation and reference material intended to be loaded into context to inform Gemini CLI's process and thinking.

**Appropriate for:** In-depth documentation, API references, database schemas, comprehensive guides, or any detailed information that Gemini CLI should reference while working.

### assets/
Files not intended to be loaded into context, but rather used within the output Gemini CLI produces.

**Appropriate for:** Templates, boilerplate code, document templates, images, icons, fonts, or any files meant to be copied or used in the final output.

---

**Any unneeded directories can be deleted.** Not every skill requires all three types of resources.
"""

EXAMPLE_SCRIPT = """#!/usr/bin/env python3

\"\"\"
Example helper script for {skill_name}

This is a placeholder script that can be executed directly.
Replace with actual implementation or delete if not needed.

Example real scripts from other skills:
- pdf/scripts/fill_fillable_fields.py - Fills PDF form fields
- pdf/scripts/convert_pdf_to_images.py - Converts PDF pages to images

Agentic Ergonomics:
- Suppress tracebacks.
- Return clean success/failure strings.
- Truncate long outputs.
\"\"\"

import sys

def main():
    try:
        # TODO: Add actual script logic here.
        # This could be data processing, file conversion, API calls, etc.

        # Example output formatting for an LLM agent
        sys.stdout.write("Success: Processed the task.\\n")
    except Exception as err:
        # Trap the error and output a clean message instead of a noisy stack trace
        sys.stderr.write(f"Failure: {{err}}\\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
"""

EXAMPLE_REFERENCE = """# Reference Documentation for {skill_title}

This is a placeholder for detailed reference documentation.
Replace with actual reference content or delete if not needed.

## Structure Suggestions

### API Reference Example
- Overview
- Authentication
- Endpoints with examples
- Error codes

### Workflow Guide Example
- Prerequisites
- Step-by-step instructions
- Best practices
"""


def title_case(name):
    return " ".join(word.capitalize() for word in name.split("-"))


def main():
    parser = argparse.ArgumentParser(description="Skill Initializer")
    parser.add_argument("skill_name", help="Name of the skill to create")
    parser.add_argument(
        "--path",
        required=True,
        help="Base path where the skill directory will be created",
    )
    args = parser.parse_args()

    skill_name = args.skill_name
    base_path = Path(args.path).resolve()

    if os.sep in skill_name or "/" in skill_name or "\\" in skill_name:
        print("❌ Error: Skill name cannot contain path separators.")
        sys.exit(1)

    skill_dir = base_path / skill_name

    # Additional check to ensure the resolved skill_dir is actually inside base_path
    if not str(skill_dir).startswith(str(base_path)):
        print("❌ Error: Invalid skill name or path.")
        sys.exit(1)

    if skill_dir.exists():
        print(f"❌ Error: Skill directory already exists: {skill_dir}")
        sys.exit(1)

    skill_title = title_case(skill_name)

    try:
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "scripts").mkdir()
        (skill_dir / "references").mkdir()
        (skill_dir / "assets").mkdir()

        with open(skill_dir / "SKILL.md", "w") as f:
            f.write(
                SKILL_TEMPLATE.format(skill_name=skill_name, skill_title=skill_title)
            )

        script_path = skill_dir / "scripts" / "example_script.py"
        with open(script_path, "w") as f:
            f.write(EXAMPLE_SCRIPT.format(skill_name=skill_name))
        os.chmod(script_path, 0o755)

        with open(skill_dir / "references" / "example_reference.md", "w") as f:
            f.write(EXAMPLE_REFERENCE.format(skill_title=skill_title))

        with open(skill_dir / "assets" / "example_asset.txt", "w") as f:
            f.write("Placeholder for assets.")

        print(f"✅ Skill '{skill_name}' initialized at {skill_dir}")
    except Exception as err:
        print(f"❌ Error: {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
