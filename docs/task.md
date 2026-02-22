# adk-cli Development Task List

## Phase 0: Planning & Architecture
- [x] Initial Research: gemini-cli architecture
- [x] Research: Storage & Persistence patterns
- [x] Refine Implementation Plan
    - [x] Split architecture doc into manageable chunks
    - [x] Define Bootstrapping MVP requirements
- [x] Configure Dev Container (.devcontainer)
- [x] Get User Approval on MVP Plan

## Phase 1: Bootstrapping MVP (Completed)
- [x] Core Orchestration
    - [x] Create ADK Runner wrapper (`adk_cli/main.py`)
    - [x] Implement CLI entry point via `click`
- [x] Security Policy Engine
    - [x] Implement `CustomPolicyEngine`
    - [x] Implement `SecurityPlugin` for tool interception
- [x] Minimal TUI
    - [x] Interactive input loop via **Textual**
    - [x] Markdown response rendering
- [x] Essential Tools
    - [x] Port/Enable `read_file`
    - [x] Port/Enable `write_file`
    - [x] Port/Enable `grep`/`find`
    - [x] Port/Enable `bash`
- [x] Persistent Storage & Project Context
    - [x] Implement `get_adk_home()` and ensure `~/.adk/` exists
    - [x] Implement Project Registry (`projects.json`) to track workspace roots and generate Short IDs
    - [x] Replace `InMemorySessionService` with `SqliteSessionService` using `~/.adk/sessions.db`
    - [x] Update CLI to auto-detect the project and resume the most recent session for that project by default
    - [x] Add CLI commands to list and delete sessions
    - [x] Add garbage collection command (`sessions gc`) for old sessions
    - [x] Implement session locking to prevent clobbering by multiple CLI instances
    - [x] Implement `config` command to manage global settings
    - [x] Verify persistence: Ensure the agent remembers context across restarts

## Phase 2: Self-Building (In Progress)
- [x] Use `adk-cli` to implement `edit` tool (Diff/Patch)
- [ ] Implement TUI Triage & Redesign (Live Activity Tray) - See [docs/tui_redesign_plan.md](docs/tui_redesign_plan.md)
- [ ] Enhance TUI with status bars and structured output
- [ ] Implement full workspace/global storage provider

## Phase 3: Advanced Orchestration (Insights from Claude Code)
- [ ] Implement multi-phase `discovery` vs. `act` workflow.
- [ ] Implement `run_subagent` tool and delegate roles (`explorer`, `reviewer`) based on the [Skills vs. Sub-agents Strategy](implementation_plan.md#skills-vs-sub-agents-strategy).
- [ ] Add external hook support to `SecurityPlugin`.
- [ ] Implement interactive "Clarification Loop" in the TUI.
- [ ] Project-level skill discovery from `.adk/skills/`.

## Phase 4: Integrity & Advanced Merging (Insights from Nano-Claw)
- [ ] Implement structured TOML/Env-aware modification tools.
- [ ] Support three-way merging for `edit_file` to handle drift.
- [ ] Add atomic "undo/rollback" capability for failed multi-file edits.
