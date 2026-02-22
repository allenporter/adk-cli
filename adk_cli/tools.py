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


def get_essential_tools() -> list[Callable[..., Any] | BaseTool | BaseToolset]:
    """
    Returns a list of FunctionTool instances for essential filesystem operations.
    """
    return [
        FunctionTool(ls),
        FunctionTool(cat),
        FunctionTool(write_file),
        FunctionTool(grep),
    ]
