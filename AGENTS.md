# Agent Instructions for `adk-cli` Development

This document provides context and guidelines for agents working on the `adk-cli` codebase itself.

## Project Overview
`adk-cli` is a high-performance, terminal-based agentic development kit. It uses the **Textual** framework for its TUI and is designed to provide a "Gemini-like" interleaved conversation experience.

## Core Architectural Principles
1.  **Async-First**: All I/O-bound tools and TUI updates must be asynchronous. Use `asyncio.to_thread` for legacy synchronous library calls to avoid blocking the Textual main loop.
2.  **Interleaved UI**: The TUI (`adk_cli/tui.py`) uses a "Flow" model. Thoughts, tool calls, and results are appended dynamically to the conversation scroll area as they happen.
3.  **Graceful Degradation**: Tools should handle errors gracefully and return informative strings rather than crashing the agent loop.
4.  **Hierarchical Discovery**: Agents and skills are discovered by walking up the directory tree from the current working directory to the project root.

## Development Workflows
- **Scripts**: Always use the `./script/` directory for lifecycle tasks:
  - `./script/lint`: Format and lint code.
  - `./script/test`: Run the `pytest` suite.
  - `./script/bootstrap`: Install dependencies.
- **TUI Debugging**: Textual has a built-in console for debugging. Run with `textual console` in one terminal and `devtools=True` logic in the app.

## Coding Standards
- **Markup**: When sending text to the TUI that contains user or tool-generated content, ALWAYS use `rich.markup.escape()` to prevent `MarkupError`.
- **Typing**: Use static type hints throughout the project.
- **Styling**: Maintain the Gemini-inspired aesthetic:
  - Agent prefix: `✦`
  - Thoughts: Italicized with a left border.
  - Tools: Compact, inline widgets with borders.

## Memory & State
- **Scratchpad**: Use `.adk/scratchpad.md` for persistent cross-session notes or complex task planning.
- **Context**: The agent automatically reads `AGENTS.md`, `GEMINI.md`, and `CLAUDE.md` from the repo root to set system instructions.
