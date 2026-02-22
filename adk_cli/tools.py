"""
Essential filesystem and shell tools for the ADK CLI agent.

Hardening Philosophy:
1.  **Output Control**: Large outputs are truncated (e.g., `cat`, `grep`, `bash`) to avoid
    overwhelming the model's context or causing terminal instability. Paging is provided
    where appropriate.
2.  **Safety & Precision**: File modifications (`edit_file`) require exact, unique matches
    to prevent accidental corruption. Destructive operations should be avoided or carefully
    wrapped.
3.  **Predictability**: Tools return structured, sorted, and well-labeled information
    (e.g., `ls` marks directories, `grep` includes line numbers) to improve model reasoning.
4.  **Robustness**: Tools handle edge cases like binary files, character encoding issues,
    and command timeouts to prevent silent or confusing failures.
5.  **Efficiency**: Batch operations (e.g., `read_many_files`) reduce tool call overhead.

Future Guidance:
- When adding tools, consider if the output could be excessively large.
- Avoid tools that allow arbitrary code execution without a specific reason.
- Prefer high-level semantic tools over low-level primitives when possible.
"""

import os
import subprocess
from typing import Any, Callable

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.function_tool import FunctionTool


def ls(directory: str = ".", show_hidden: bool = False) -> str:
    """
    Lists the files and directories in the specified path.
    Directories are suffixed with a trailing slash.
    """
    try:
        items = []
        for entry in os.scandir(directory):
            if not show_hidden and entry.name.startswith("."):
                continue
            if entry.is_dir():
                items.append(f"{entry.name}/")
            else:
                items.append(entry.name)
        items.sort()
        return "\n".join(items) if items else "No items found."
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def cat(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """
    Reads and returns the content of the file at the specified path.
    If the file is large, use start_line and end_line to read it in chunks.
    Line numbers are 1-indexed.
    """
    try:
        if not os.path.isfile(path):
            return f"Error: {path} is not a file."

        # Open file without loading everything into memory
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            broken_early = False

            # Default to showing 1000 lines if no end_line is specified
            effective_end = end_line if end_line is not None else start_line + 999

            for i, line in enumerate(f, 1):
                if i >= start_line:
                    if i > effective_end:
                        broken_early = True
                        break
                    lines.append(line)

            # If we didn't break early, check if there's at least one more line to flag truncation
            if not broken_early:
                try:
                    next_line = next(f, None)
                    if next_line is not None:
                        broken_early = True
                except (StopIteration, UnicodeDecodeError):
                    pass

        if not lines:
            if start_line > 1:
                return f"Error: file has fewer than {start_line} lines."
            return "(empty file)"

        content = "".join(lines)
        if broken_early:
            content += f"\n\n[Output truncated. Showing lines {start_line}-{effective_end}. Use start_line and end_line to read more.]"

        return content
    except UnicodeDecodeError:
        return f"Error: {path} appears to be a binary file."
    except Exception as e:
        return f"Error reading file: {str(e)}"


def read_many_files(paths: list[str]) -> str:
    """
    Reads multiple files and returns their contents in a structured format.
    """
    results = []
    for path in paths:
        content = cat(path)
        results.append(f"--- File: {path} ---\n{content}\n")
    return "\n".join(results)


def write_file(path: str, content: str) -> str:
    """
    Creates or overwrites a file at the specified path with the given content.
    """
    try:
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


def edit_file(path: str, search_text: str, replacement_text: str) -> str:
    """
    Replaces a specific, unique block of text in a file with new content.

    This tool is safer and more efficient than write_file for modifying
    existing files because it only changes the targeted section.
    """
    try:
        if not os.path.exists(path):
            return f"Error: File not found at {path}"

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        occurrences = content.count(search_text)

        if occurrences == 0:
            return (
                f"Error: search_text not found in {path}. "
                "Ensure the text matches exactly, including whitespace and indentation."
            )

        if occurrences > 1:
            return (
                f"Error: search_text found {occurrences} times in {path}. "
                "Please provide a more unique block (include surrounding lines) to target the edit."
            )

        new_content = content.replace(search_text, replacement_text)

        # Calculate line differences for descriptive summaries
        old_lines = search_text.splitlines()
        new_lines = replacement_text.splitlines()

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return f"Successfully edited {path} (+{len(new_lines)} -{len(old_lines)})"
    except Exception as e:
        return f"Error editing file: {str(e)}"


def grep(
    pattern: str, directory: str = ".", recursive: bool = True, context_lines: int = 0
) -> str:
    """
    Searches for a pattern within files in a directory.
    context_lines: Number of lines of leading and trailing context to show.
    """
    try:
        # Avoid common noise directories to speed up searches and reduce context pollution
        exclude_dirs = [
            ".git",
            ".adk",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            "build",
            "dist",
        ]

        cmd = ["grep", "-n"]
        if recursive:
            cmd.append("-r")
        if context_lines > 0:
            cmd.append(f"-C{context_lines}")

        for d in exclude_dirs:
            # Use --exclude-dir which is supported by GNU grep on Linux
            cmd.append(f"--exclude-dir={d}")

        # Use -- before the pattern to handle cases where it starts with hyphen
        cmd.extend(["--", pattern, directory])

        # Add a reasonable timeout to prevent hanging on huge project trees
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        output = result.stdout
        if not output and result.stderr:
            return f"Error running grep: {result.stderr}"

        if not output:
            return "No matches found."

        max_chars = 15000
        if len(output) > max_chars:
            truncation_msg = (
                f"\n\n[Output truncated from {len(output)} characters to {max_chars}]"
            )
            return output[:max_chars] + truncation_msg

        return output
    except subprocess.TimeoutExpired:
        return "Error: grep command timed out after 60 seconds."
    except Exception as e:
        return f"Error running grep: {str(e)}"


def bash(command: str, cwd: str = ".") -> str:
    """
    Executes a shell command and returns the combined stdout and stderr.
    The output is truncated if it exceeds 10,000 characters.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300,
        )

        combined_output = (result.stdout or "") + (
            f"\n--- STDERR ---\n{result.stderr}" if result.stderr else ""
        )

        if not combined_output.strip():
            return "Command executed successfully with no output."

        max_chars = 10000
        if len(combined_output) > max_chars:
            truncation_msg = f"\n\n[Output truncated from {len(combined_output)} characters to {max_chars}]"
            return combined_output[:max_chars] + truncation_msg

        return combined_output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 300 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"


def _get_agent_metadata(agent_name: str) -> dict[str, Any]:
    """Helper to load a specialized agent metadata from its Markdown file."""
    from pathlib import Path
    import yaml

    # Try finding the artifact in the feature-dev builtin skill first
    builtin_agent_path = (
        Path(__file__).parent
        / "skills"
        / "builtin"
        / "feature-dev"
        / "agents"
        / f"{agent_name}.md"
    )

    if builtin_agent_path.is_file():
        try:
            content = builtin_agent_path.read_text(encoding="utf-8")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    metadata = yaml.safe_load(parts[1])
                    metadata["instruction"] = parts[2].strip()
                    return metadata
            return {"instruction": content.strip()}
        except Exception:
            pass

    return {}


def _run_subagent_task(
    prompt: str, agent_name: str = "adk_subagent", fallback_instruction: str = ""
) -> str:
    """Internal helper to run a sub-agent with a specific instruction and toolset."""
    from google.adk.runners import Runner
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    from google.genai import types
    from adk_cli.agent_factory import build_adk_agent

    # Load metadata from Markdown if available
    metadata = _get_agent_metadata(agent_name)
    instruction = metadata.get("instruction") or fallback_instruction
    tool_names = metadata.get("allowed_tools")
    include_skills = metadata.get("include_skills", False)

    # Build a fresh agent configuration
    agent = build_adk_agent(
        instruction=instruction,
        tool_names=tool_names,
        include_skills=include_skills,
        agent_name=agent_name,
    )

    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name=f"adk_{agent_name}",
        session_service=session_service,
        auto_create_session=True,
    )

    content = types.Content(role="user", parts=[types.Part(text=prompt)])

    try:
        events = runner.run(
            user_id="subagent", session_id="subsession", new_message=content
        )
        report = []
        for event in events:
            if event.is_final_response() and event.content and event.content.parts:
                report.append(event.content.parts[0].text)

        return "\n".join(report) if report else "Subagent failed to return a report."
    except Exception as e:
        return f"Error in subagent: {str(e)}"


def explore_codebase(task: str) -> str:
    """
    Spawns a specialized Discovery Agent to map out the architecture or find
    specific logic. Use this for 'Where is X defined?' or 'How does Y work?'.

    This agent is restricted to read-only tools and is optimized for searching
    large amounts of data without cluttering the main conversation.
    """
    fallback_instruction = (
        "You are a specialized Code Discovery Agent. Your goal is to explore "
        "the codebase and answer the user's architectural questions. "
        "Use `ls`, `grep`, and `cat` to find definitions, patterns, and "
        "relationships. Return a concise summary of your findings."
    )

    # Note: tools and instruction are now loaded from Markdown if available
    return _run_subagent_task(
        task, agent_name="code-explorer", fallback_instruction=fallback_instruction
    )


def review_work(original_goal: str) -> str:
    """
    Spawns a specialized Code Reviewer to audit the current state of the
    files against the user's initial request.

    Use this before finishing a task to ensure no bugs or security flaws
    were introduced. Return a list of 'Critical Issues' and 'Suggestions'.
    """
    fallback_instruction = (
        "You are a Senior Code Reviewer. Audit the changes in the current "
        "directory against the user's original goal. Look for bugs, "
        "security flaws, and inconsistencies. Be critical and objective. "
        "Format your output as: \n### Critical Issues\n...\n### Suggestions\n..."
    )

    # Reviewer needs discovery tools and bash to run tests/checks
    return _run_subagent_task(
        f"Review the current changes against this goal: {original_goal}",
        agent_name="code-reviewer",
        fallback_instruction=fallback_instruction,
    )


def design_architecture(task: str) -> str:
    """
    Spawns a specialized Architecture Agent to design implementation blueprints.
    Use this to get detailed file-by-file plans, component responsibilities,
    and build sequences.
    """
    fallback_instruction = (
        "You are a specialized Code Architect. Your goal is to design "
        "comprehensive implementation blueprints. Specify every file to "
        "create or modify, component responsibilities, and data flow."
    )

    # Architect needs discovery tools to understand patterns
    return _run_subagent_task(
        task, agent_name="code-architect", fallback_instruction=fallback_instruction
    )


def manage_todo_list(todo_list: list[dict[str, Any]]) -> str:
    """
    Update the session's structured todo list to track progress and plan tasks.
    Each todo should have 'id' (int), 'title' (str), and 'status' (not-started, in-progress, completed).
    Limit 'in-progress' to 1 at a time.

    Note: The todo list is part of the session's ephemeral state and is not
    persisted across different sessions or to external files.

    Returns: A summary of the current todo list with visual indicators.
    """
    formatted = []
    status_map = {
        "not-started": "[ ]",
        "in-progress": "[>]",
        "completed": "[x]",
    }

    for item in todo_list:
        status_icon = status_map.get(item.get("status", "not-started"), "?")
        status_icon = status_icon.ljust(3)
        formatted.append(
            f"{status_icon} {item.get('id', '?')}: {item.get('title', '???')}"
        )

    # No real persistence required here as the Supervisor agent's history
    # manages the state through tool calls.
    return "Todo list updated:\n" + "\n".join(formatted)


def run_subagent(task: str, agent_name: str = "adk_subagent") -> str:
    """
    Spawns a specialized sub-agent to handle a specific task.
    This is useful for delegating complex sub-tasks or exploring parts of the codebase
    without losing the main conversation context.

    The sub-agent will have its own session and toolset based on its name/type.

    Args:
        task: The specific task or question for the sub-agent to address.
        agent_name: The identifier for the sub-agent. This determines its
                   instruction set and available tools (e.g., 'code-explorer',
                   'code-architect', 'code-reviewer').
    """
    return _run_subagent_task(task, agent_name=agent_name)


def get_essential_tools() -> list[Callable[..., Any] | BaseTool | BaseToolset]:
    """
    Returns a list of FunctionTool instances for essential filesystem operations.
    """
    return [
        FunctionTool(ls),
        FunctionTool(cat),
        FunctionTool(read_many_files),
        FunctionTool(write_file),
        FunctionTool(edit_file),
        FunctionTool(grep),
        FunctionTool(bash),
        FunctionTool(explore_codebase),
        FunctionTool(design_architecture),
        FunctionTool(review_work),
        FunctionTool(manage_todo_list),
        FunctionTool(run_subagent),
    ]
