import os
import subprocess
from typing import Any, Callable

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.function_tool import FunctionTool


def ls(directory: str = ".") -> str:
    """
    Lists the files and directories in the specified path.
    """
    try:
        items = os.listdir(directory)
        return "\n".join(items) if items else "No items found."
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def cat(path: str) -> str:
    """
    Reads and returns the content of the file at the specified path.
    """
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def write_file(path: str, content: str) -> str:
    """
    Creates or overwrites a file at the specified path with the given content.
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
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

        with open(path, "r") as f:
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

        with open(path, "w") as f:
            f.write(new_content)

        return f"Successfully edited {path}"
    except Exception as e:
        return f"Error editing file: {str(e)}"


def grep(pattern: str, directory: str = ".", recursive: bool = True) -> str:
    """
    Searches for a pattern within files in a directory.
    """
    try:
        cmd = ["grep", "-r" if recursive else "", pattern, directory]
        cmd = [c for c in cmd if c]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.stdout else "No matches found."
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


def get_essential_tools() -> list[Callable[..., Any] | BaseTool | BaseToolset]:
    """
    Returns a list of FunctionTool instances for essential filesystem operations.
    """
    return [
        FunctionTool(ls),
        FunctionTool(cat),
        FunctionTool(write_file),
        FunctionTool(edit_file),
        FunctionTool(grep),
        FunctionTool(bash),
    ]
