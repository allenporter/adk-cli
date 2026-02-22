# gemini-cli Architecture Review & google-adk Adaptation Plan

This plan outlines the core architecture of `gemini-cli` and provides a strategy for reproducing its key components using `google-adk`.

## Architecture Overview

`gemini-cli` is built as a monorepo with a clear separation between the UI layer and the core agentic logic.

### 1. Core Logic (`packages/core`)
The "brain" of the application, responsible for:
- **Orchestration**: `GeminiClient` manages the session, history, and the agentic loop.
- **Turn Management**: `Turn` handles a single interaction, including streaming model responses and collecting tool calls.
- **Tool Execution**: `CoreToolScheduler` manages the lifecycle of tool calls (Validation -> Approval -> Execution).
- **Policy Engine**: Implemented via ADK `SecurityPlugin`, deciding if a tool call should be allowed, denied, or requires user confirmation.
- **Prompt Composition**: `PromptProvider` dynamically assembles the system prompt from snippets and context (interactive mode, skills, tools, user memory).

### 2. UI Layer (`packages/cli`)
A terminal user interface (TUI) built with:
- **React + Ink**: Renders the UI components to the terminal.
- **AppContainer**: The main layout component managing the state of the CLI.
- **State Management**: Uses React hooks and contexts to manage UI state, which interacts with the `GeminiClient`.

### 3. Extensibility
- **Skills**: Markdown-based instructions and tools that can be dynamically activated.
- **Agents**: Specialized sub-agents defined in markdown with their own system prompts and toolsets.
- **MCP (Model Context Protocol)**: Support for external tool servers.

### 4. Storage & Persistence
The system uses a layered storage approach to balance global settings with project-specific context:
- **Global Storage (`~/.gemini/`)**:
  - `projects.json`: A registry mapping project absolute paths to unique **Short IDs**. This is critical for organizing session history and logs without using long, path-based folder names.
  - `settings.json`: User-level configuration and globally registered MCP servers.
  - `mcp-server-enablement.json`: Persistent toggle state for MCP servers.
  - `mcp-oauth-tokens.json`: Secure storage for tool-related credentials.
  - `acknowledgments/`: Tracks user approval for running project-specific agents or extensions.
- **Workspace Storage (`<project-root>/.gemini/`)**:
  - `settings.json`: Project-specific overrides (e.g., preferred tools, local MCP servers).
  - `policies/`: Local security rules for tool execution.
  - `agents/`: Local agent definitions.
- **Session & History**:
  - `~/.gemini/history/<short-id>/`: Permanent chat history and telemetry.
  - `~/.gemini/tmp/<short-id>/`: Volatile state like shell history and checkpoints.

---

## Adaptation Plan for google-adk

`google-adk` also supports tools and skills, making it a natural fit for reproducing `gemini-cli` features.

### Component Mapping

| gemini-cli Concept | google-adk Equivalent / Approach |
| :--- | :--- |
| `GeminiClient` (Orchestrator) | Use `google-adk`'s core agent orchestration features. |
| `BaseDeclarativeTool` | Implement as `google-adk` tools. |
| `SkillManager` / Skills (.md) | Use `google-adk` builtin skills support. |
| `AgentLoader` / Agents (.md) | Model as specialized `google-adk` agents or skills. |
| `CoreToolScheduler` | Use ADK `SecurityPlugin` with a `CustomPolicyEngine`. |
| `PromptProvider` | Adopt the snippet-based composition logic in the system instructions. |
| `Storage` / Persistence | Implement a directory-based storage provider that handles global vs. workspace scopes and project ID mapping. |

### Proposed Steps for Reproduction

#### 1. Analyze Key Tools
Identify the most critical tools in `gemini-cli` to port first:
- `read_file`, `write_file`, `edit` (Base file operations)
- `shell` (Execute terminal commands)
- `grep`, `glob` (Search and discovery)
- `web_fetch`, `web_search` (Internet access)

#### 2. Skill & Agent Porting
Convert `gemini-cli` skills (located in `.agents/skills`) to `google-adk` compatible skills. This involves mapping the YAML frontmatter and the markdown body to the expected `google-adk` format.

#### 3. Orchestration Adaptation
Reproduce the "session management" and "history compression" logic if `google-adk` doesn't provide them out-of-the-box. `gemini-cli`'s approach of sending IDE context and delta updates is a key performance feature worth porting.

#### 4. UI Layer (Optional)
If a TUI is required, one could build a wrapper around the `google-adk` agent using Ink, similar to `packages/cli`.

#### 5. Policy Engine & Human-in-the-loop Implementation
To repro `gemini-cli`'s safety features, we will implement a `CustomPolicyEngine` subclass of ADK's `BasePolicyEngine`:
- **`evaluate()` Logic**: Intercept every `ToolCall`.
- **Outcome Mapping**:
  - `PolicyOutcome.ALLOW`: For read-only tools or when `--permission-mode auto`.
  - `PolicyOutcome.CONFIRM`: Triggers the HITL hook, prompting the user in the TUI to approve/deny the specific tool execution.
  - `PolicyOutcome.DENY`: Explicitly block high-risk tools (e.g., `rm -rf /`) based on user-defined blocklists.
- **Plugin Integration**: Initialize the `InMemoryRunner` with a `SecurityPlugin` wrapping our `CustomPolicyEngine`.

---

## CLI Interface Design

To match the "Claude Code" experience, `adk-cli` will implement a familiar command and flag structure.

### 1. Primary Commands
| Command | Result |
| :--- | :--- |
| `adk` | Launches the interactive TUI session. |
| `adk "query"` | Executes a one-off agentic task interactively. |
| `adk -p "query"` | **Print Mode**: Executes a task and outputs result to stdout without a TUI. |
| `adk -c` / `--continue` | Resumes the most recent session. |
| `adk -r <id>` / `--resume` | Resumes a specific named or ID-based session. |
| `adk agents` | Lists and manages active sub-agents and skills. |
| `adk mcp` | Manages Model Context Protocol server connections. |

### 2. Key Flags
- **Context**:
  - `--add-dir <path>`: Include additional directories in the working set.
- **Model & Budget**:
  - `--model <name>`: Switch between specific Gemini models (e.g., `pro`, `flash`).
  - `--max-turns <n>`: Cap the number of tool execution loops.
  - `--max-budget-usd <amount>`: Safety cap on session costs.
- **Prompting**:
  - `--system-prompt <text|file>`: Replace the base instructions.
  - `--append-system-prompt <text|file>`: Add context-specific rules (e.g., "Always use Python 3.12").
- **Workflow**:
  - `--permission-mode <plan|auto|ask>`:
    - `plan`: Agent creates a detailed plan for review before executing.
    - `auto`: Direct execution for trusted environments.
- **Output**:
  - `--output-format <text|json>`: For integration with other scripts.

---

## Verification Plan

### Manual Verification
- **Codebase Review**: Verify the mapping of `gemini-cli` services to `google-adk` concepts with the user.
- **Tool Porting**: Demonstrate a single tool (e.g., `read_file`) running within a `google-adk` agent.
- **Skill Porting**: Demonstrate a simple skill being activated and influencing the agent's behavior.

> [!IMPORTANT]
> Since this is a planning and research task, the primary verification is the user's review and approval of the architectural understanding and the proposed migration path.
