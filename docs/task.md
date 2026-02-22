# adk-cli Development Task List

## Phase 0: Planning & Architecture
- [x] Initial Research: gemini-cli architecture
- [x] Research: Storage & Persistence patterns
- [/] Refine Implementation Plan
    - [x] Split architecture doc into manageable chunks
    - [x] Define Bootstrapping MVP requirements
- [ ] Get User Approval on MVP Plan

## Phase 1: Bootstrapping MVP
- [ ] Core Orchestration
    - [ ] Create basic ADK Runner wrapper
    - [ ] Implement simple CLI entry point (yargs/commander)
- [ ] Essential Tools
    - [ ] Port `read_file`
    - [ ] Port `write_file`
    - [ ] Port `grep`/`glob`
- [ ] Basic Persistence
    - [ ] Simple Short ID mapping
    - [ ] Basic settings loading
- [ ] Minimal TUI/REPL
    - [ ] Basic input loop
    - [ ] Streaming response output

## Phase 2: Self-Building
- [ ] Use `adk-cli` to implement `edit` tool
- [ ] Use `adk-cli` to implement Security Policy Engine
- [ ] Use `adk-cli` to implement full React/Ink TUI
