# Memory Strategy for CLAW (Computer-Like Agent Workflow)

This document outlines the architectural strategy for implementing "Working Memory" and "Blackboard" patterns in the ADK/CLAW ecosystem.

## 1. The Core Philosophy: Filesystem as Primary Memory

Unlike traditional LLM applications that rely on specialized vector databases or hidden internal states, CLAW treats the **filesystem** as its primary source of truth and working memory.

### Benefits of Filesystem Memory:
- **Observability**: Humans can see exactly what the agent is "thinking" or "remembering" by looking at the project files.
- **Persistence**: Memory naturally survives session restarts.
- **Portability**: Different agents (and different tools) can share state by reading the same files.
- **Tool Compatibility**: Standard tools like `grep`, `cat`, and `ls` become memory retrieval tools.

## 2. Memory Tiers

| Tier | Implementation | Scope | Retention |
| :--- | :--- | :--- | :--- |
| **Short-Term** | LLM Context / History | Current Turn | Ephemeral |
| **Working Memory** | `.adk/scratchpad.md` / `manage_todo_list` | Active Task | Per-task / Per-session |
| **Project Memory** | `ARCHITECTURE.md`, `TODO.md` | Whole Project | Indefinite |
| **Tool State** | `.adk/state.json` | Tool-specific (e.g., shell CWD) | Cross-session |

## 3. Existing Memory Tools in ADK-CLI

The current implementation already provides basic working memory through the following:

- **`manage_todo_list`**: A structured tool used by the Supervisor to track the current phase and progress. While currently stored in conversation history, it serves as the "Primary Mission Memory."
- **Session History (SQLite)**: Persists the entire conversation stream, allowing the agent to "remember" previous turns when a session is resumed.
- **Agent Compaction**: A built-in mechanism that summarizes old conversation history to fit within the context window, acting as a "Long-term Narrative Memory."

## 3. The "Blackboard" Strategy

To enable effective multi-agent collaboration without context bloat, we follow these patterns:

### A. The "Notebook" Pattern (Single Agent)
Agents should maintain a `.adk/scratchpad.md` file. They use `write_file` and `edit_file` to keep notes, track sub-task progress, and store intermediate results that would otherwise be lost in the conversation history after compaction.

### B. The "Skill-Based" Memory (Cross-Agent)
Rather than a centralized memory API, we build **Skills** that manage specific domains of knowledge.
- **Discovery Skill**: Manages a map of the codebase.
- **Planning Skill**: Manages the `TODO.md` and dependency graph.

- **Audit Skill**: Tracks historical changes and "lessons learned" from previous bug fixes.

### C. Persistent Shell State
A critical gap in standard CLI agents is the loss of `cd` and environment state.
- **Strategy**: Implement a wrapper tool that persists the `CWD` and `ENV` to a state file (`.adk/shell_state.json`) and restores it before every execution.

## 4. Architectural Considerations

1. **Race Conditions**: In a multi-agent "CLAW" environment, agents must be careful not to overwrite the same memory file simultaneously. We use file-locking (via `portalocker`) in the tool layer to prevent corruption.
2. **Context Injection**: When a sub-agent is spawned, the parent should not just pass a prompt, but also the path to the current `scratchpad.md` so the sub-agent has the latest "Working Memory."
3. **Compaction-Awareness**: As the supervisor's history is compacted, it must "flush" critical information from the conversation into the filesystem memory to ensure it isn't lost during summarization.

## 5. Next Steps for CLAW Implementation

- [ ] Develop a `shell-persistent` tool that maintains environment state.
- [ ] Update `feature-dev` agent instructions to prioritize reading/writing to `.adk/scratchpad.md`.
- [ ] Create a "Memory Cleanup" skill to prevent `.adk/` from becoming a dumping ground of stale information.
