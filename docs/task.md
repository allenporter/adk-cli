# adk-cli Development Task List

## Phase 0: Planning & Architecture
- [x] Initial Research: gemini-cli architecture
- [x] Research: Storage & Persistence patterns
- [/] Refine Implementation Plan
    - [x] Split architecture doc into manageable chunks
    - [x] Define Bootstrapping MVP requirements
- [x] Configure Dev Container (.devcontainer)
- [ ] Get User Approval on MVP Plan

## Phase 1: Bootstrapping MVP (In Progress)
- [x] Core Orchestration
    - [x] Create ADK Runner wrapper (`adk_cli/main.py`)
    - [x] Implement CLI entry point via `click`
- [x] Security Policy Engine
    - [x] Implement `CustomPolicyEngine`
    - [x] Implement `SecurityPlugin` for tool interception
- [x] Minimal TUI
    - [x] Interactive input loop via **Textual**
    - [x] Markdown response rendering
- [/] Essential Tools (Remaining)
    - [/] Port/Enable `read_file`
    - [/] Port/Enable `write_file`
    - [/] Port/Enable `grep`/`find`
- [ ] Basic Persistence
    - [ ] Simple Short ID mapping
    - [ ] Basic settings loading

## Phase 2: Self-Building
- [ ] Use `adk-cli` to implement `edit` tool (Diff/Patch)
- [ ] Enhance TUI with status bars and structured output
- [ ] Implement full workspace/global storage provider
