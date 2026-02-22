# adk-cli Architecture & Implementation Strategy

This document provides a high-level overview of the `adk-cli` architecture, derived from `gemini-cli`, and maps out the strategy for reproducing it using `google-adk`.

## Modular Documentation
To keep the project manageable, the specific implementation details are split across several documents:

1. [High-Level Architecture & Strategy](implementation_plan.md) (This document)
2. [Bootstrapping MVP Plan](bootstrapping_plan.md): The minimal path to a self-building CLI.
3. [Task Tracking](task.md): Current development progress and roadmap.

---

## core Architecture Reference

`gemini-cli` is built as a monorepo with a clear separation between the UI layer and the core agentic logic.

### 1. Core Logic (`packages/core`)
The "brain" of the application, responsible for:
- **Orchestration**: `GeminiClient` manages the session, history, and the agentic loop.
- **Turn Management**: `Turn` handles a single interaction, including streaming model responses and collecting tool calls.
- **Tool Execution**: `CoreToolScheduler` manages the lifecycle of tool calls (Validation -> Approval -> Execution).
- **Policy Engine**: Decidies if a tool call should be allowed, denied, or requires user confirmation.
- **Prompt Composition**: `PromptProvider` dynamically assembles the system prompt from snippets and context.

### 2. Extensibility
- **Skills**: Markdown-based instructions and tools.
- **Agents**: Specialized sub-agents defined in markdown.
- **MCP (Model Context Protocol)**: Support for external tool servers.

### 3. Storage & Persistence
- **Global Storage (`~/.gemini/`)**: Projects registry (Short IDs), settings, MCP enablement, OAuth tokens, and acknowledgments.
- **Workspace Storage (`<project-root>/.gemini/`)**: Local overrides, policies, and local agents.
- **Session & History**: Organized by project Short ID to manage logs and volatile state.

---

## Adaptation Strategy for google-adk

`google-adk` supports tools and skills natively, providing the perfect foundation.

| gemini-cli Concept | google-adk Equivalent / Approach |
| :--- | :--- |
| `GeminiClient` | Use `google-adk`'s core orchestration. |
| `SkillManager` | Use `google-adk` builtin skills. |
| `CoreToolScheduler` | ADK `SecurityPlugin` + `CustomPolicyEngine`. |
| `PromptProvider` | Adopt the snippet-based composition logic. |
| `Storage` | Custom directory-based storage provider for global/workspace scopes. |

## Bootstrapping Goal: "The Self-Building CLI"
The primary implementation goal is to reach **Phase 2: Self-Building** as quickly as possible. This means the CLI should have enough tool power to:
1. Read its own source code.
2. Implement new tools and features via patching.
3. run its own build and test scripts.
