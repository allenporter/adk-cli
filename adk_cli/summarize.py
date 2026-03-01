import os
import re
from typing import Any, Dict, Optional


from rich.markup import escape
from google.adk.tools.base_tool import BaseTool


def summarize_tool_call(
    name: str, args: Dict[str, Any], tool: Optional[BaseTool] = None
) -> str:
    """
    Generate a human-readable summary of what a tool is about to do.
    """
    # 1. Try to use tool metadata if available
    if tool and hasattr(tool, "callable") and tool.callable:
        metadata = getattr(tool.callable, "_adk_tool_metadata", None)
        if metadata and metadata.summary_template:
            try:
                # Sanitize args for formatting (escape rich markup)
                clean_args = {k: escape(str(v)) for k, v in args.items()}
                return metadata.summary_template.format(**clean_args)
            except (KeyError, IndexError):
                # Fallback to hardcoded or generic if template formatting fails
                pass

    # 2. Hardcoded fallbacks
    if name == "cat":
        path = args.get("path", "unknown file")
        start = args.get("start_line", 1)
        end = args.get("end_line")
        range_str = f"lines {start}-{end}" if end else f"starting at line {start}"
        return f"Reading {escape(os.path.basename(path))} ({range_str})"

    if name == "edit_file":
        path = args.get("path", "unknown file")
        return f"Editing {escape(os.path.basename(path))}"

    if name == "write_file":
        path = args.get("path", "unknown file")
        return f"Writing {escape(os.path.basename(path))}"

    if name == "ls":
        directory = args.get("directory", ".")
        return f"Listing {escape(directory)}"

    if name == "bash":
        command = args.get("command", "")
        # Use simple color coding for commands if possible or just bold
        return (
            f"Execute command: [bold magenta]{escape(command.strip())}[/bold magenta]"
        )

    if name == "grep":
        pattern = args.get("pattern", "")
        directory = args.get("directory", ".")
        return f"Search for '[bold]{escape(pattern)}[/bold]' in [dim]{escape(directory)}[/dim]"

    if name == "read_many_files":
        paths = args.get("paths", [])
        count = len(paths)
        if count == 1:
            return f"Read [bold]{escape(os.path.basename(paths[0]))}[/bold]"
        files_list = ", ".join([os.path.basename(p) for p in paths[:3]])
        if count > 3:
            files_list += f" and {count - 3} more"
        return f"Read {count} files ([dim]{escape(files_list)}[/dim])"

    if name == "run_subagent":
        task = args.get("task", "")
        agent_name = args.get("agent_name", "subagent")
        # Truncate task for display
        task_summary = task.strip().splitlines()[0] if task else ""
        if len(task_summary) > 50:
            task_summary = task_summary[:47] + "..."
        return f"Running [bold]{escape(agent_name)}[/bold]: {escape(task_summary)}"

    # Default fallback
    return f"Executing {escape(name)}"


def summarize_tool_call_args(name: str, args: Dict[str, Any]) -> str:
    """
    Generate a string representing the tool's input arguments.
    """
    if name == "bash":
        return args.get("command", "")
    if name == "edit_file":
        return f"Path: {args.get('path')}\n\nSearch:\n{args.get('search_text')}\n\nReplacement:\n{args.get('replacement_text')}"
    if name == "write_file":
        return f"Path: {args.get('path')}\n\nContent:\n{args.get('content')}"
    if name == "grep":
        return f"Pattern: {args.get('pattern')}\nDirectory: {args.get('directory')}\nRecursive: {args.get('recursive')}"
    if name == "run_subagent":
        return f"Agent: {args.get('agent_name')}\nTask: {args.get('task')}"

    # Generic stringification for others
    if not args:
        return "(no arguments)"
    return "\n".join(f"{k}: {v}" for k, v in args.items())


def summarize_tool_result(name: str, args: Dict[str, Any], result: str) -> str:
    """
    Generate a human-readable summary of what a tool achieved.
    """
    if name == "run_subagent":
        agent_name = args.get("agent_name", "subagent")
        return f"[bold]{escape(agent_name)}[/bold] finished"
    if name == "edit_file":
        # Look for the line count information in the result message
        # e.g., "Successfully edited path (+2 -1)"
        match = re.search(r"\(\+(\d+) -(\d+)\)", result)
        path = args.get("path", "file")
        if match:
            added, removed = match.groups()
            return f"Edited {escape(os.path.basename(path))} (+{added} -{removed})"
        return f"Edited {escape(os.path.basename(path))}"

    if name == "write_file":
        path = args.get("path", "file")
        return f"Wrote {escape(os.path.basename(path))}"

    if name == "cat":
        path = args.get("path", "file")
        lines = result.strip().splitlines()
        # Filter out truncation messages
        content_lines = [
            line for line in lines if not line.startswith("[Output truncated")
        ]
        return f"Read {len(content_lines)} lines from {escape(os.path.basename(path))}"

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
            return f"No items found in {escape(directory)}"
        return f"Listed {len(items)} items in {escape(directory)}"

    if name == "bash":
        command = args.get("command", "")
        # Truncate command for display
        cmd_summary = command.strip().splitlines()[0] if command else ""
        if len(cmd_summary) > 50:
            cmd_summary = cmd_summary[:47] + "..."

        if "Error" in result:
            return f"Bash command '{escape(cmd_summary)}' failed"
        return f"Command '{escape(cmd_summary)}' completed"

    # Default fallback - can't really summarize arbitrary results well
    return "Done"
