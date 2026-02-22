# adk-cli: Bootstrapping MVP Plan

The goal of this MVP is to create a functional CLI that can orchestration a `google-adk` agent with enough tools to modify its own source code and verify its work.

## Proposed Changes

### 1. Minimal Core Orchestration
- [NEW] `src/core/runner.py`: A thin wrapper around `google-adk`'s `InMemoryRunner`.
- [NEW] `src/main.py`: CLI entry point using `click` or `argparse` to handle basic inputs and flags (`--prompt`, `--model`).

### 2. Essential Toolset
We will implement the following tools as ADK tools:
- `read_file`: Read file contents.
- `write_file`: Create new files.
- `edit_file`: (Initially simplified) Use a patch-based approach.
- `shell`: Run shell commands with standard security guards.
- `ls`/`glob`: File discovery.

### 3. Basic Security Policy
- Implementation of a `SimplePolicyEngine` that:
  - Defaults to `ALLOW` for read-only operations.
  - Defaults to `CONFIRM` for write/shell operations.
  - Implementation of the `prompt_user` hook for the TUI (or a simple readline interface for now).

### 4. Basic Persistence
- Minimal implementation of the `Short ID` project mapping.
- Storage of session logs in `~/.adk/history/`.

## Verification Plan

### Automated Tests
- Run the MVP with a prompt like "create a file named hello.txt with content 'world'".
- Verify the file is created and the policy engine correctly prompted for confirmation.

### Manual Verification
- Attempt to use the MVP CLI to implement a new tool (e.g., `grep`).
