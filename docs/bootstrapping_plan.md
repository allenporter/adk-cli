# adk-cli: Bootstrapping MVP Plan

The goal of this MVP is to create a functional CLI that can orchestrate a `google-adk` agent with enough tools to modify its own source code and verify its work.

## Current Progress & Implementation

### 1. Core Orchestration
- [x] `adk_cli/main.py`: CLI entry point using `click`. Handles basic inputs and flags (`--permission-mode`, `--model`, `--print`).
- [x] Integrated `google.adk.runners.Runner` with `LlmAgent` and `InMemorySessionService`.

### 2. Security Policy (Implemented)
- [x] `adk_cli/policy.py`: Implements `CustomPolicyEngine` and `SecurityPlugin`.
  - Supports `plan`, `auto`, and `ask` modes.
  - Automatically allows safe tools (e.g., `ls`, `view_file`) and requires confirmation for sensitive operations in `ask` mode.
  - Integrated with ADK's `before_tool_callback`.

### 3. TUI Implementation (Foundation Ready)
- [x] `adk_cli/tui.py`: Rich TUI built with **Textual**.
  - Interactive chat interface with markdown rendering.
  - Supports initial query injection from the CLI.

## Remaining MVP Tasks

### 4. Essential Toolset
We need to implement/port the following tools to the CLI's internal agent:
- `read_file`: Use ADK's file tools.
- `write_file`: Use ADK's file tools.
- `edit_file`: Patch-based approach.
- `shell`: Command execution with security guards.
- `ls`/`find`: File discovery.

### 5. Persistence & Context
- [ ] Session persistence (beyond in-memory).
- [ ] Short ID project mapping for workspace context.
- [ ] Global/Local settings management.

## Verification Plan

### Automated Tests
- [x] `tests/test_policy.py`: Verifies security policy logic.
- [x] `tests/test_cli.py`: Verifies CLI argument parsing and TUI launching.
- [ ] End-to-end test: Prompt the agent to create a file and verify its creation.

### Manual Verification
- [ ] Use `adk "create a test.txt file"` and verify the confirmation prompt and file output.
