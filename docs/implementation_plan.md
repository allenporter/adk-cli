# adk-cli Architecture & Implementation Strategy

This document provides a high-level overview of the `adk-cli` architecture, derived from `gemini-cli`, and maps out the strategy for reproducing it using `google-adk`.

## Modular Documentation
To keep the project manageable, the specific implementation details are split across several documents:

1. [High-Level Architecture & Strategy](implementation_plan.md) (This document)
2. [Bootstrapping MVP Plan](bootstrapping_plan.md): The minimal path to a self-building CLI.
3. [Task Tracking](task.md): Current development progress and roadmap.

---

## Core Architecture Reference

`gemini-cli` is built as a clear separation between the UI layer and the core agentic logic.

### 1. Core Logic (`adk_cli/`)
The "brain" of the application, responsible for:
- **Orchestration**: `Runner` manages the session, history, and the agentic loop.
- **Tool Execution**: `SecurityPlugin` manages the lifecycle of tool calls (Validation -> Approval -> Execution).
- **Policy Engine**: `CustomPolicyEngine` decides if a tool call should be allowed, denied, or requires user confirmation.
- **Tools**: `adk_cli/tools.py` provides essential filesystem tools (`read_file`, `write_file`, `ls`, `grep`) wrapped in `FunctionTool`.

### 2. UI Layer (`adk_cli/tui.py`)
- **Textual TUI**: A rich terminal user interface built with the **Textual** framework, providing markdown rendering and interactive chat.

### 3. Extensibility
- **Skills**: Markdown-based instructions and tools.
- **Agents**: Specialized sub-agents defined in markdown.
- **MCP (Model Context Protocol)**: Support for external tool servers.

### 4. Storage & Persistence
- **Global Storage (`~/.adk/`)**: Projects registry (Short IDs), settings, MCP enablement, OAuth tokens, and acknowledgments.
- **Workspace Storage (`<project-root>/.adk/`)**: Local overrides, policies, and local agents.
- **Session & History**: Organized by project Short ID to manage logs and volatile state.

---

## Adaptation Strategy for google-adk

`google-adk` supports tools and skills natively, providing the perfect foundation.

| gemini-cli Concept | google-adk Equivalent / Approach |
| :--- | :--- |
| `GeminiClient` | Use `google-adk`'s core orchestration (Runner). |
| `SkillManager` | Use `google-adk` builtin skills. |
| `CoreToolScheduler` | ADK `SecurityPlugin` + `CustomPolicyEngine`. |
| `PromptProvider` | Adopt the snippet-based composition logic. |
| `Storage` | Custom directory-based storage provider for global/workspace scopes. |
| `TUI` | Python **Textual** framework. |

### Essential Toolset
#### [NEW] [tools.py](file:///Users/allen/Development/adk-cli/adk_cli/tools.py)
Implementation of ADK tools for filesystem operations:
- `ls`: List directory contents.
- `read_file` (or `cat`): Read file content.
- `write_file`: Create or overwrite files.
- `grep`: Search for strings within files.
