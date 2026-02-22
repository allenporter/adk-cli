import os
import re
from typing import Any, Dict


def summarize_tool_call(name: str, args: Dict[str, Any]) -> str:
    """
    Generate a human-readable summary of what a tool is about to do.
    """
    if name == "cat":
        path = args.get("path", "unknown file")
        start = args.get("start_line", 1)
        end = args.get("end_line")
        range_str = f"lines {start}-{end}" if end else f"starting at line {start}"
        return f"Reading {os.path.basename(path)} ({range_str})"

    if name == "edit_file":
        path = args.get("path", "unknown file")
        return f"Editing {os.path.basename(path)}"

    if name == "write_file":
        path = args.get("path", "unknown file")
        return f"Writing {os.path.basename(path)}"

    if name == "ls":
        directory = args.get("directory", ".")
        return f"Listing {directory}"

    if name == "bash":
        command = args.get("command", "")
        # Truncate command for display
        cmd_summary = command.strip().splitlines()[0] if command else ""
        if len(cmd_summary) > 50:
            cmd_summary = cmd_summary[:47] + "..."
        return f"Running bash: {cmd_summary}"

    if name == "grep":
        pattern = args.get("pattern", "")
        directory = args.get("directory", ".")
        return f"Searching for '{pattern}' in {directory}"

    if name == "read_many_files":
        paths = args.get("paths", [])
        count = len(paths)
        if count == 1:
            return f"Reading {os.path.basename(paths[0])}"
        return f"Reading {count} files"

    # Default fallback
    return f"Executing {name}"


def summarize_tool_result(name: str, args: Dict[str, Any], result: str) -> str:
    """
    Generate a human-readable summary of what a tool achieved.
    """
    if name == "edit_file":
        # Look for the line count information in the result message
        # e.g., "Successfully edited path (+2 -1)"
        match = re.search(r"\(\+(\d+) -(\d+)\)", result)
        path = args.get("path", "file")
        if match:
            added, removed = match.groups()
            return f"Edited {os.path.basename(path)} (+{added} -{removed})"
        return f"Edited {os.path.basename(path)}"

    if name == "write_file":
        path = args.get("path", "file")
        return f"Wrote {os.path.basename(path)}"

    if name == "cat":
        path = args.get("path", "file")
        lines = result.strip().splitlines()
        # Filter out truncation messages
        content_lines = [
            line for line in lines if not line.startswith("[Output truncated")
        ]
        return f"Read {len(content_lines)} lines from {os.path.basename(path)}"

    if name == "grep":
        lines = result.strip().splitlines()
        # Filter out error or no matches messages
        if "No matches found" in result:
            return "No matches found"
        if "Error" in result:
            return "Grep failed"

        # Grep usually returns match lines, but might include truncation info
        count = sum(1 for line in lines if not line.startswith("[Output truncated"))
        return f"Found {count} matches"

    if name == "ls":
        items = result.strip().splitlines()
        directory = args.get("directory", ".")
        if "No items found" in result:
            return f"No items found in {directory}"
        return f"Listed {len(items)} items in {directory}"

    if name == "bash":
        command = args.get("command", "")
        # Truncate command for display
        cmd_summary = command.strip().splitlines()[0] if command else ""
        if len(cmd_summary) > 50:
            cmd_summary = cmd_summary[:47] + "..."

        if "Error" in result:
            return f"Bash command '{cmd_summary}' failed"
        return f"Command '{cmd_summary}' completed"

    # Default fallback - can't really summarize arbitrary results well
    return "Done"
