# TUI Redesign: Live Activity Tray

This document outlines the plan to separate the conversation history from tool activity in the TUI, providing a cleaner and more professional user experience.

## Goal
To maintain a high-signal-to-noise ratio in the main chat window. Conversation ("👤 You" and "🤖 Agent" text) should occupy the primary scrollable area, while "work-in-progress" (tool calls, status updates, thinking processes) should be relegated to a dedicated, volatile "Activity Tray" at the bottom of the screen.

## Proposed Layout

```text
+---------------------------------------+
| Header (Project, Session, Clock)      |
+---------------------------------------+
|                                       |
|  [CHAT HISTORY WINDOW]                |
|  (User & Agent text messages only)    |
|                                       |
+---------------------------------------+
|  [ACTIVITY TRAY]                      |
|  🛠️ Reading main.py...                |
|  ✅ Read 120 lines from main.py       |
+---------------------------------------+
|  > [USER INPUT]                       |
+---------------------------------------+
| Footer (Bindings)                     |
+---------------------------------------+
```

## Implementation Strategy

### 1. Activity Tray Container
- **Component**: Create an `#activity-tray` container (Vertical or ScrollableContainer) in `ChatScreen.compose`.
- **Visibility**: The tray should be hidden or collapsed when no turnover is active.
- **Constraints**: Limit the maximum height (e.g., `max-height: 10`) to prevent it from consuming the entire screen.

### 2. Turn Lifecycle Management
- **Turn Start**: Clear the `#activity-tray` whenever the user submits a new query.
- **Execution Phase**:
    - Tool calls (`🛠️`) and summarized results (`✅`) are mounted into `#activity-tray`.
    - Thinking processes (`💭`) are also shown here as they stream.
- **Turn End**:
    - Option A (Archive): Summarize the tray's final state into a single compact line (e.g., `(Completed 4 tool calls)`) and move it to the bottom of the `#chat-scroll`.
    - Option B (Clear): Simply clear the tray to focus on the Agent's final textual response.

### 3. Messaging Refactor
- Update `adk_cli/tui.py`:
    - Modify `Message` rendering to be even more compact when appearing in the tray.
    - Update `ChatScreen.process_query` to target `#activity-tray` for `role="tool"` and `role="status"` messages.

## Expected Benefits
- **Readability**: Long conversations remain legible without large gaps filled by tool technicalities.
- **Focus**: The user's eye stays on the prompt and the response.
- **Trust**: Seeing the tray animate with activity provides confirmation that the agent is working without cluttering the permanent log.

## Future Considerations
- **Process Cycling**: Allow clicking the tray summary to expand or "pop out" a full-screen history of all tool activity for that turn.
- **Progress Bars**: Integrate real-world progress (e.g., percentage of files read/searched) into the tray.
