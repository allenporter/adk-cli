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
#### [NEW] [tools.py](adk_cli/tools.py)
Implementation of ADK tools for filesystem operations:
- `ls`: List directory contents.
- `read_file` (or `cat`): Read file content.
- `write_file`: Create or overwrite files.
- `grep`: Search for strings within files.

---

## Current Status & Lessons Learned (Phase 1)

As of the completion of the Bootstrapping MVP, the following core components are operational and have provided key architectural insights:

### 1. Robust File Operations
The `adk_cli/tools.py` module now includes a refined set of tools (`ls`, `cat`, `write_file`, `edit_file`, `bash`) that handle common pitfalls like large output truncation and exact-match safety for edits.
- **Insight**: Direct file editing is the most fragile operation. We've moved towards exact-match search/replace, but Phase 2 will focus on more advanced patching.

### 2. TUI & Streaming
The Textual-based TUI (`adk_cli/tui.py`) successfully handles asynchronous streaming of agent responses while maintaining a responsive UI.
- **Insight**: Tool call visualization is critical for user trust. We now explicitly show `🛠️ Executing: ...` in the chat history.

### 3. Policy-Based Security
The `SecurityPlugin` and `CustomPolicyEngine` provide a flexible way to intercept tool calls.
- **Insight**: The "Confirmation Loop" (interfacing ADK's `request_confirmation` with a Textual `ModalScreen`) is a powerful pattern for human-in-the-loop safety without breaking the agentic flow.

### 4. Persistent Project Context
By combining `SqliteSessionService` with a project registry (`projects.json`), the CLI now automatically resumes the last session for a given directory.
- **Insight**: Mapping physical paths to logical "Short IDs" is essential for managing history in a multi-project development environment.

---

## Strategic Insights from Claude Code Analysis

A review of the `claude-code` codebase and its plugin architecture suggests several high-impact features for `adk-cli`:

### 1. Multi-Phase Orchestration
Complex tasks should be broken down into discrete phases (Discovery -> Exploration -> Architecture -> Implementation -> Review). This reduces "hallucination" and ensures the agent has adequate context before writing code.

### 2. Specialized Personnel (Sub-Agents)
The use of specialized persona-based agents (`code-explorer`, `code-architect`, `code-reviewer`) can be mapped directly to `google-adk` skills. This allows defining distinct system prompts and tool restrictions for different phases of the development lifecycle.
- **Update (Phase 2)**: The `feature-dev` skill has been implemented, formalizing these personas as sub-agents. Observations include the need for careful context management when running multiple parallel reviewers and ensuring the `manage_todo_list` tool is robust enough to support multi-phase orchestration.

### 3. Pre-Tool Validation (Hooks)
Extending the `SecurityPlugin` to support external validation scripts (like `claude-code`'s hooks). These scripts can intercept tool calls to enforce project-specific safety rules or suggest better tool alternatives (e.g., suggesting `ripgrep` over `grep`).
- **Observation**: Highly specialized reviewers (like the `code-reviewer` in `feature-dev`) use confidence scoring (0-100) to filter noise. This pattern should be encouraged across all validation-focused skills.

### 4. Interactive Ambiguity Resolution
Explicitly pausing execution when ambiguities are found during the "Discovery" phase. This "Clarification Loop" ensures that requirements are fully understood before any sensitive operations are performed.

### 5. Seamless Skill Overrides
Supporting project-level skill discovery in `.adk/skills/`, allowing developers to easily extend the CLI's capabilities with custom, repo-specific agent logic.

---

## Skills vs. Sub-agents Strategy

Choosing between augmenting the main agent (Skills) and delegating to a separate context (Sub-agents) is critical for context hygiene and performance.

| Persona | Implementation | Rationale |
| :--- | :--- | :--- |
| **`code-explorer`** | **Sub-agent** | Isolation: Prevents "context pollution" from raw file reads and `ls` outputs. Returns a concise summary to the main agent. |
| **`code-architect`** | **Skill** | Persistence: The main agent must "live" by these design principles throughout the implementation phase. |
| **`code-reviewer`** | **Sub-agent** | Objectivity: Provides a "blind" fresh check of the changes without the main agent's intermediate bias. |

### Technical Approach in ADK
- **Skills**: Augmented into the system prompt of the primary `Runner`.
- **Sub-agents**: Launched via a `run_subagent` tool which spawns a new `Runner` instance with a separate session and instructions, returning only the resulting "report" to the caller.

---

## Code Integrity & Modification Strategy (Insights from Nano-Claw)

While `google-adk` provides the base for file operations, `nano-claw` demonstrates advanced "Integrity-First" patterns that can be adopted to make `adk-cli` more resilient.

### 1. Structured Data Merging
Rather than treating all files as blobs of text, use specialized handlers for structured configuration files.
- **Implementation**: Provide dedicated tools (e.g., `add_python_dependency`, `modify_env_variable`) that use structured parsers (like `tomlkit` or `python-dotenv`) to ensure the file remains valid after modification, bypassing expensive and error-prone LLM regex "patching."

### 2. Three-Way Merge for Drift Resolution
Maintain a baseline of files to detect the difference between "What the agent thought was there" and "What is actually there."
- **Implementation**: When `edit_file` is called, perform a three-way merge (Base vs. Current vs. Proposed) to automatically reconcile changes if the user has manually edited the file in parallel.

### 3. Atomic Tool Transactions (Rollbacks)
Complex multi-file modifications should be reversible.
- **Implementation**: Before a destructive tool execution (like `edit_file` or `bash`), create a temporary backup. If the operation fails (e.g., a merge conflict or a lint error post-edit), the agent should have a `rollback` tool to restore the previous state instantly.
