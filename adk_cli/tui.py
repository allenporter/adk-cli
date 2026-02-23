import logging
import asyncio
from typing import Optional, Dict, Any, Callable
from textual import on
from textual.app import App, ComposeResult, Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header,
    Footer,
    Input,
    Static,
    Label,
    Button,
    LoadingIndicator,
    Collapsible,
    RadioButton,
    RadioSet,
)
from textual.binding import Binding
from textual.reactive import reactive
from rich.markdown import Markdown
from google.adk.runners import Runner
from google.genai import types


from rich.markup import escape

from adk_cli.confirmation import confirmation_manager
from adk_cli.status import status_manager
from adk_cli.summarize import summarize_tool_call, summarize_tool_result
from adk_cli.constants import APP_NAME

logger = logging.getLogger(__name__)


class InlineConfirmation(Static):
    """An inline widget to confirm or deny an action."""

    def __init__(
        self,
        hint: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
        future: Optional[asyncio.Future] = None,
    ):
        super().__init__()
        self.hint = hint
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.future = future
        self._resolved = False

    def compose(self) -> ComposeResult:
        with Vertical(classes="confirmation-container"):
            yield Label(f"  {self.hint}", classes="confirmation-hint")
            with RadioSet(id="confirmation-choice"):
                yield RadioButton("Approve", id="radio-approve", value=True)
                yield RadioButton("Deny", id="radio-deny")
            yield Button("Confirm", variant="primary", id="confirm-button")

    @on(RadioSet.Changed)
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        # We can handle logic here if needed, but we'll wait for button press
        pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self._resolved:
            return

        if event.button.id == "confirm-button":
            radio_set = self.query_one("#confirmation-choice", RadioSet)
            # Find which one is selected
            result = radio_set.pressed_index == 0  # "Approve" is index 0
            self._resolve(result)

    def on_key(self, event: Any) -> None:
        """Handle 'y' and 'n' keys for confirmation."""
        if self._resolved:
            return
        if event.key == "y":
            self._resolve(True)
        elif event.key == "n":
            self._resolve(False)

    def _resolve(self, result: bool) -> None:
        self._resolved = True
        if self.future and not self.future.done():
            self.future.set_result(result)

        # Update UI to reflect the choice
        self.remove_class("active")
        self.add_class("resolved")
        status = "✅ Approved" if result else "❌ Denied"

        # Remove the interaction elements
        try:
            self.query_one("#confirmation-choice").remove()
            self.query_one("#confirm-button").remove()
        except Exception:
            pass

        self.query_one(".confirmation-hint", Label).update(f"{status}: {self.hint}")


class ThoughtMessage(Collapsible):
    """A widget to display agent thoughts."""

    text = reactive("")

    def __init__(self, text: str):
        self._streaming = False
        self.text = text
        self._content_widget = Static(text, classes="thought-content")
        super().__init__(self._content_widget, title="Thinking...")
        self.add_class("thought-container")
        self._titles = ["Thinking...", "Reasoning...", "Processing...", "Reflecting..."]
        self._title_index = 0

    @on(Collapsible.Expanded)
    def on_expanded(self) -> None:
        self.scroll_visible()

    def start_streaming(self) -> None:
        self._streaming = True
        self.collapsed = False
        self._title_timer = self.set_interval(2.0, self._cycle_title)

    def _cycle_title(self) -> None:
        if self._streaming:
            self._title_index = (self._title_index + 1) % len(self._titles)
            self.title = self._titles[self._title_index]

    def finish_streaming(self) -> None:
        self._streaming = False
        if hasattr(self, "_title_timer"):
            self._title_timer.stop()
        self.title = "Thought Process"
        self._content_widget.update(Markdown(self.text))
        # Keep expanded after finishing so user can see it
        self.collapsed = False

    def watch_text(self, old_text: str, new_text: str) -> None:
        if self._streaming:
            self._content_widget.update(new_text)
        else:
            self._content_widget.update(Markdown(new_text))


class ToolMessage(Collapsible):
    """A widget to display tool outputs."""

    def __init__(self, summary: str, raw_output: str):
        # Limit output to prevent lag
        if len(raw_output) > 10000:
            raw_output = raw_output[:10000] + "\n\n... (output truncated) ..."

        self._content_widget = Static(raw_output, classes="tool-content")
        super().__init__(self._content_widget, title=f"🛠️ {summary}")
        self.add_class("tool-container")
        self.collapsed = True  # Start collapsed as requested

    @on(Collapsible.Expanded)
    def on_expanded(self) -> None:
        self.scroll_visible()


class Message(Static):
    """A widget to display a chat message."""

    # layout=False (default) avoids an expensive full layout pass on every token.
    text = reactive("")

    def __init__(self, text: str, role: str):
        super().__init__()
        self.role = role
        self._streaming = False
        self.text = text
        self.add_class(role)

    def start_streaming(self) -> None:
        """Switch to cheap plain-text rendering while tokens are arriving."""
        self._streaming = True

    def finish_streaming(self) -> None:
        """Stream is done — do one final markdown render."""
        self._streaming = False
        self.update(self._markdown_renderable())

    def _markdown_renderable(self) -> Any:
        """Build the full Markdown renderable (used once, when streaming ends)."""
        if self.role == "status":
            return self.text
        if self.role == "tool":
            return f"🛠️  [bold]{escape(self.text)}[/bold]"
        prefix = "✦ Agent" if self.role == "agent" else "👤 You"

        return Markdown(f"### {prefix}\n\n{self.text}")

    def watch_text(self, old_text: str, new_text: str) -> None:
        """Trigger a refresh when the text changes."""
        if self._streaming:
            # Skip markdown parsing while tokens are streaming in — just show
            # plain text so we avoid O(n) re-parsing on every token delta.
            prefix = "✦ Agent" if self.role == "agent" else "👤 You"
            self.update(f"{prefix}\n\n{new_text}")
        else:
            self.update(self._markdown_renderable())

    def render(self) -> Markdown:
        return self._markdown_renderable()


class PendingQuery(Static):
    """A widget for a queued query that hasn't been sent yet."""

    def __init__(self, text: str, on_remove: Callable[[str], None]):
        super().__init__()
        self.text = text
        self.on_remove = on_remove

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label(f"Pending: {self.text}", id="pending-text")
            yield Button("x", id="remove-btn", variant="error")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "remove-btn":
            self.on_remove(self.text)
            await self.remove()


class ChatScreen(Screen):
    """The main chat interface screen."""

    CSS = """
    Screen {
        background: #121212;
    }

    #main-container {
        height: 1fr;
    }

    #chat-area {
        height: 1fr;
    }

    #chat-scroll {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
        border: none;
    }

    .thought-container {
        margin: 0 4;
        border: none;
    }

    .thought-container > Contents {
        color: #666;
        padding: 0 1;
        border-left: solid #444;
        text-style: italic;
        max-height: 15;
        overflow-y: auto;
    }

    .thought-container CollapsibleTitle {
        color: #666;
        background: transparent;
        padding: 0;
    }

    .thought-container CollapsibleTitle:hover {
        color: $primary;
        background: transparent;
    }

    .thought-container CollapsibleTitle:focus {
        background: $accent;
        color: $text;
        text-style: bold;
    }

    .confirmation-container {
        margin: 0 4;
        padding: 0 1;
        background: transparent;
        border-left: solid $warning;
        min-height: 1;
        height: auto;
    }

    .confirmation-container.resolved {
        border-left: solid $success;
        opacity: 0.5;
    }

    .confirmation-hint {
        margin: 0;
        color: $warning;
        height: auto;
    }

    #confirmation-choice {
        background: transparent;
        border: none;
        padding: 0;
        margin: 0;
        height: auto;
    }

    #confirm-button {
        margin: 1 0;
        height: 1;
        width: 15;
        border: none;
        padding: 0 1;
    }

    .confirmation-tool {
        background: transparent;
        padding: 0;
        margin: 0;
        height: auto;
    }

    .confirmation-buttons {
        height: auto;
        margin: 0;
        align: left middle;
        layout: horizontal;
    }

    .confirmation-buttons Button {
        margin: 0 2 0 0;
        height: 1;
        min-width: 8;
        border: none;
        padding: 0 1;
    }

    .confirmation-buttons Label {
        width: 1fr;
        margin-right: 2;
    }

    .tool-container {
        margin: 0 4;
        border: none;
    }

    .tool-container > Contents {
        background: #1a1a1a;
        color: #007acc;
        padding: 1;
        border-left: solid #007acc;
    }

    .tool-container CollapsibleTitle {
        color: #007acc;
        background: transparent;
        padding: 0;
    }

    .tool-container CollapsibleTitle:hover {
        background: transparent;
        text-style: underline;
    }

    .tool-container CollapsibleTitle:focus {
        background: $accent;
        color: $text;
        text-style: bold;
    }

    PendingQuery {
        background: $surface;
        border: dashed;
        margin: 1 2;
        padding: 0 1;
        height: 3;
    }

    PendingQuery Horizontal {
        height: 1;
        margin: 0;
    }

    PendingQuery #pending-text {
        width: 1fr;
        color: $text-muted;
        content-align: left middle;
    }

    PendingQuery #remove-btn {
        width: 3;
        min-width: 3;
        height: 1;
        border: dashed $error;
        padding: 0;
        margin: 0;
    }

    #status-bar {
        height: 1;
        background: $surface;
        padding: 0 1;
        border-bottom: solid $primary;
    }

    #status-bar Label {
        margin-right: 2;
        color: $text-muted;
    }

    #input-container {
        height: 3;
        border-top: solid #333;
        background: #1e1e1e;
        padding: 0 2;
    }

    Input {
        border: none;
        background: transparent;
        width: 1fr;
        height: 1;
        margin: 1 0;
        min-width: 0;
        padding: 0;
    }

    #input-container Label {
        color: #007acc;
        margin: 1 0;
        width: auto;
        padding: 0;
        text-style: bold;
    }

    Message {
        margin: 1 0;
        padding: 1;
    }

    Message.agent {
        background: transparent;
    }

    Message.user {
        background: #1e1e1e;
        border-left: solid #28a745;
    }

    Message.status {
        margin: 0 4;
        padding: 0;
        background: transparent;
        color: #ffa500;
        border: none;
        opacity: 0.8;
    }

    Message.tool {
        margin: 0 4;
        padding: 0 1;
        background: #1a1a1a;
        color: #007acc;
        border-left: solid #007acc;
    }

    #chat-scroll {
        scrollbar-gutter: stable;
    }

    #chat-scroll:focus {
        border: tall $accent;
            }

    #loading-container {
        height: 3;
        align: left middle;
        margin: 1 4;
    }

    LoadingIndicator {
        height: 1;
        width: auto;
        color: $primary;
    }

    #loading-status {
        margin-left: 1;
        color: $primary;
        content-align: left middle;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "app.quit", "Quit", show=False),
        Binding("tab", "focus_next", "Focus Next", show=False),
        Binding("shift+tab", "focus_previous", "Focus Previous", show=False),
        Binding("up", "scroll_up", "Scroll Up", show=False),
        Binding("down", "scroll_down", "Scroll Down", show=False),
        Binding("pageup", "page_up", "Page Up", show=False),
        Binding("pagedown", "page_down", "Page Down", show=False),
    ]

    def action_focus_next(self) -> None:
        """Focus the next widget without forced scrolling."""
        self.app.action_focus_next()

    def action_focus_previous(self) -> None:
        """Focus the previous widget without forced scrolling."""
        self.app.action_focus_previous()

    def action_scroll_up(self) -> None:
        self.query_one("#chat-scroll").scroll_up()

    def action_scroll_down(self) -> None:
        self.query_one("#chat-scroll").scroll_down()

    def action_page_up(self) -> None:
        self.query_one("#chat-scroll").scroll_page_up()

    def action_page_down(self) -> None:
        self.query_one("#chat-scroll").scroll_page_down()

    def __init__(
        self,
        runner: Optional[Runner],
        user_id: str,
        session_id: str,
        initial_query: Optional[str],
    ):
        super().__init__()
        self.runner = runner
        self.user_id = user_id
        self.session_id = session_id
        self.initial_query = initial_query
        self._pending_queries: list[str] = []
        self._is_processing = False

    def remove_pending(self, text: str) -> None:
        """Removes a query from the pending list."""
        if text in self._pending_queries:
            self._pending_queries.remove(text)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            with Vertical(id="chat-area"):
                with Horizontal(id="status-bar"):
                    yield Label(f"Project: [bold]{self.user_id}[/]", id="project-label")
                    yield Label(
                        f"Session: [bold]{self.session_id}[/]", id="session-label"
                    )
                chat_scroll = Vertical(id="chat-scroll")
                chat_scroll.can_focus = True
                with chat_scroll:
                    yield Message(
                        "Welcome to **ADK CLI**! How can I help you today?\n\n"
                        "Type `/quit` or press **Ctrl+C** to exit.",
                        role="agent",
                    )
                with Horizontal(id="input-container"):
                    yield Label("✦ ")
                    yield Input(
                        placeholder="Ask anything... (or /quit to exit)",
                        id="user-input",
                    )
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#user-input", Input).focus()
        await self.load_history()
        if self.initial_query:
            self._pending_queries.append(self.initial_query)
            self.run_worker(self._process_pending())

    async def _process_pending(self) -> None:
        """Processes all pending queries as a single turn."""
        if self._is_processing or not self._pending_queries:
            return

        self._is_processing = True
        try:
            # Join all pending queries into a single Turn
            combined_query = "\n\n".join(self._pending_queries)
            self._pending_queries.clear()

            # Clean up any pending UI widgets
            chat_scroll = self.query_one("#chat-scroll", Vertical)
            for widget in chat_scroll.query(PendingQuery):
                await widget.remove()

            await self.process_query(combined_query)
        finally:
            self._is_processing = False
            # If new queries arrived while processing, trigger another run
            if self._pending_queries:
                self.run_worker(self._process_pending())
            else:
                try:
                    self.query_one("#user-input", Input).focus()
                except Exception:
                    pass

    async def load_history(self) -> None:
        """Loads and displays history for the current session."""
        if not self.runner or not self.runner.session_service:
            return

        try:
            session = await self.runner.session_service.get_session(
                app_name=APP_NAME, user_id=self.user_id, session_id=self.session_id
            )
            if not session or not session.events:
                return

            chat_scroll = self.query_one("#chat-scroll", Vertical)

            for event in session.events:
                role = "user" if event.author == "user" else "agent"
                if not event.content or not event.content.parts:
                    continue

                for part in event.content.parts:
                    p_text = getattr(part, "text", None)
                    p_thought = getattr(part, "thought", None)

                    if p_thought:
                        # Reconstruct thought if it exists
                        msg = ThoughtMessage(p_thought)
                        await chat_scroll.mount(msg)
                        msg.finish_streaming()
                        # History thoughts should probably be collapsed to save space
                        msg.collapsed = True

                    if p_text:
                        msg = Message(p_text, role=role)
                        await chat_scroll.mount(msg)
                        msg.finish_streaming()

            chat_scroll.scroll_end()
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")

    async def handle_initial_query(self, query: str) -> None:
        await self.process_query(query)

    def add_status_message(self, text: str) -> None:
        """Adds a subtle status message to the chat scroll."""
        msg = Message(text, role="status")
        # Ensure we are modifying UI on the right loop/thread
        self.app.call_from_thread(self._mount_status, msg)

    def _mount_status(self, msg: Message) -> None:
        chat_scroll = self.query_one("#chat-scroll", Vertical)
        chat_scroll.mount(msg)
        chat_scroll.scroll_end()

    async def process_query(self, query: str) -> None:
        if not self.runner:
            return

        logger.debug(f"--- [Query Processing Started] --- Query: {query}")
        chat_scroll = self.query_one("#chat-scroll", Vertical)
        await chat_scroll.mount(Message(query, role="user"))
        chat_scroll.scroll_end()

        # Remove any existing loading indicator before mounting a new one
        try:
            old_loading = self.query_one("#loading-container")
            await old_loading.remove()
        except Exception:
            pass

        loading_container = Horizontal(
            LoadingIndicator(),
            Label("Thinking...", id="loading-status"),
            id="loading-container",
        )
        await chat_scroll.mount(loading_container)
        chat_scroll.scroll_end()

        # Input text content specifically from the agent/model
        current_agent_message = None
        current_thought_message = None
        current_tool_message = None
        # Keep track of tool call arguments so we can summarize the results correctly
        pending_args: Dict[Optional[str], Dict[str, Any]] = {}

        chat_scroll = self.query_one("#chat-scroll", Vertical)

        new_message = types.Content(role="user", parts=[types.Part(text=query)])

        try:
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=new_message,
            ):
                logger.debug(f"Received Runner event type {type(event)}: {event}")
                if event.content and event.content.parts:
                    # In ADK events, role can sometimes be None for deltas.
                    # We check for explicitly 'user' role to skip mounting tool/user response text.
                    role = event.content.role
                    for part in event.content.parts:
                        # Capture both regular text and thinking process if present
                        # We specifically check for the existence of the field to avoid
                        # warnings from the SDK when accessing .text on function_call parts.
                        part_text = None
                        part_thought = None

                        if not part.function_call and not part.function_response:
                            part_text = getattr(part, "text", None)
                            part_thought = getattr(part, "thought", None)

                        if part_text or part_thought:
                            if role == "user":
                                logger.debug(
                                    "Skipping text part for agent bubble (explicit user/tool role)"
                                )
                                continue

                            if part_thought:
                                if current_thought_message is None:
                                    logger.debug(
                                        "Initializing new thought message bubble"
                                    )
                                    current_thought_message = ThoughtMessage("")
                                    current_thought_message.start_streaming()
                                    await chat_scroll.mount(
                                        current_thought_message,
                                        before=loading_container,
                                    )

                                # Thought content is in part_thought, not part_text
                                current_thought_message.text += part_thought
                                chat_scroll.scroll_end()

                                # Update loading status with a snippet of the thought
                                snippet = part_thought.strip().replace("\n", " ")
                                if len(snippet) > 30:
                                    snippet = snippet[:27] + "..."
                                try:
                                    loading_container.query_one(
                                        "#loading-status", Label
                                    ).update(f"Reasoning: {snippet}")
                                except Exception:
                                    pass

                            if part_text and isinstance(part_text, str):
                                # If we switch from thought to text, finish the thought message
                                if current_thought_message:
                                    current_thought_message.finish_streaming()
                                    current_thought_message = None
                                # Collapse previous tools
                                if current_tool_message:
                                    current_tool_message.collapsed = True
                                    current_tool_message = None

                                if current_agent_message is None:
                                    logger.debug(
                                        "Initializing new agent message bubble"
                                    )
                                    current_agent_message = Message("", role="agent")
                                    current_agent_message.start_streaming()
                                    # Mount before the indicator to keep indicator at the bottom
                                    await chat_scroll.mount(
                                        current_agent_message, before=loading_container
                                    )

                                current_agent_message.text += part_text
                                try:
                                    loading_container.query_one(
                                        "#loading-status", Label
                                    ).update("Typing...")
                                except Exception:
                                    pass

                        if part.function_response:
                            # Collapse previous reasoning or tools
                            if current_thought_message:
                                current_thought_message.finish_streaming()
                                current_thought_message = None
                            if current_tool_message:
                                current_tool_message.collapsed = True
                                current_tool_message = None

                            # If we have an active agent message, "close" it
                            if current_agent_message:
                                current_agent_message.finish_streaming()
                                current_agent_message = None

                            # We show a clean summary of what the tool achieved.
                            resp_data = part.function_response.response
                            if resp_data:
                                call_name = part.function_response.name or "unknown"
                                # Use stored arguments for better context
                                call_args = pending_args.get(call_name, {})

                                result_raw = (
                                    resp_data.get("result")
                                    or resp_data.get("output")
                                    or str(resp_data)
                                )
                                summary = summarize_tool_result(
                                    call_name, call_args, str(result_raw)
                                )

                                current_tool_message = ToolMessage(
                                    summary, str(result_raw)
                                )
                                await chat_scroll.mount(
                                    current_tool_message,
                                    before=loading_container,
                                )
                                chat_scroll.scroll_end()
                                try:
                                    loading_container.query_one(
                                        "#loading-status", Label
                                    ).update("Processing results...")
                                except Exception:
                                    pass
                    # Scroll once per event, not per individual text part.
                    if current_agent_message is not None:
                        chat_scroll.scroll_end()

                if event.get_function_calls():
                    # If we have an active agent message, "close" it
                    if current_agent_message:
                        current_agent_message.finish_streaming()
                        current_agent_message = None
                    if current_thought_message:
                        current_thought_message.finish_streaming()
                        current_thought_message = None
                    if current_tool_message:
                        current_tool_message.collapsed = True
                        current_tool_message = None

                    for call in event.get_function_calls():
                        logger.debug(f"Requesting function call execution: {call.name}")

                        # Store arguments for later result summarization
                        call_name = call.name or "unknown"
                        pending_args[call_name] = call.args or {}

                        # Skip generic display for confirmation
                        if call.name == "adk_request_confirmation":
                            continue

                        try:
                            loading_container.query_one(
                                "#loading-status", Label
                            ).update(f"Running {call_name}...")
                        except Exception:
                            pass

                        # Use a more descriptive tool display
                        display_name: str = summarize_tool_call(
                            call_name, call.args or {}
                        )

                        # Check if this tool call was already mounted (e.g. via thinking reasoning)
                        # We only mount it here if it wasn't specifically a confirmation tool
                        # and we haven't already shown a status update for it.
                        await chat_scroll.mount(
                            Message(display_name, role="tool"), before=loading_container
                        )
                        chat_scroll.scroll_end()

            logger.debug("--- [Query Finished Successfully] ---")
            # Finalise the last agent message bubble with a proper markdown render.
            if current_agent_message is not None:
                current_agent_message.finish_streaming()
            if current_thought_message is not None:
                current_thought_message.finish_streaming()
            if current_tool_message is not None:
                current_tool_message.collapsed = True
            # Final scroll to ensure everything is visible
            chat_scroll.scroll_end()
        except Exception as e:
            logger.exception("Error during runner execution:")
            await chat_scroll.mount(
                Message(f"❌ Error: {str(e)}", role="agent"), before=loading_container
            )
            chat_scroll.scroll_end()
        finally:
            await loading_container.remove()
            try:
                # No longer disabling/enabling here, as the consumer manages the flow
                self.query_one("#user-input", Input).focus()
            except Exception:
                pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if text.lower() == "/quit":
            self.app.exit()
            return

        input_widget = self.query_one("#user-input", Input)
        input_widget.value = ""

        # If we are already processing, just add to pending list and show UI
        if self._is_processing:
            self._pending_queries.append(text)
            chat_scroll = self.query_one("#chat-scroll", Vertical)
            # Find the loading indicator to mount before it
            try:
                loading = self.query_one("#loading-container")
                await chat_scroll.mount(
                    PendingQuery(text, self.remove_pending), before=loading
                )
            except Exception:
                await chat_scroll.mount(PendingQuery(text, self.remove_pending))
            chat_scroll.scroll_end()
        else:
            self._pending_queries.append(text)
            self.run_worker(self._process_pending())


class AdkTuiApp(App):
    """The main TUI for adk-cli."""

    BINDINGS = [Binding("ctrl+c", "quit", "Quit", show=False)]

    def __init__(
        self,
        initial_query: Optional[str] = None,
        runner: Optional[Runner] = None,
        user_id: str = "default_user",
        session_id: str = "default_session",
    ):
        super().__init__()
        self.initial_query = initial_query
        self.runner = runner
        self.user_id = user_id
        self.session_id = session_id

    async def on_mount(self) -> None:
        # Register the callbacks with the global managers
        confirmation_manager.register_callback(self.ask_confirmation)
        status_manager.register_callback(self.show_status_update)

        self.push_screen(
            ChatScreen(
                runner=self.runner,
                user_id=self.user_id,
                session_id=self.session_id,
                initial_query=self.initial_query,
            )
        )

    def show_status_update(self, message: str) -> None:
        """
        Handle a status update from the system.
        """
        try:
            if isinstance(self.screen, ChatScreen):
                self.screen.add_status_message(message)
        except Exception:
            # Fallback for when the ChatScreen isn't the active screen
            pass

    async def ask_confirmation(
        self,
        req_id: str,
        hint: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Displays an inline widget to ask for user confirmation.
        """
        if not isinstance(self.screen, ChatScreen):
            return False

        # Hide loading indicator while confirming
        loading_container = None
        try:
            loading_container = self.screen.query_one("#loading-container")
            loading_container.display = False
        except Exception:
            pass

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        chat_scroll = self.screen.query_one("#chat-scroll", Vertical)

        # Create the inline confirmation widget
        conf = InlineConfirmation(hint, tool_name, tool_args, future)
        conf.can_focus = True

        # We need to decide where to mount it.
        # Ideally, it should be at the end of the current chat scroll.
        # If there's a loading indicator, we mount it BEFORE the indicator.
        if loading_container:
            await chat_scroll.mount(conf, before=loading_container)
        else:
            await chat_scroll.mount(conf)

        conf.focus()
        chat_scroll.scroll_end()

        # Wait for user interaction
        result = await future

        # Restore loading indicator
        if loading_container:
            loading_container.display = True

        # The InlineConfirmation widget handles its own UI updates upon resolution.
        return result

    async def on_shutdown(self) -> None:
        """Perform cleanup actions before the application exits."""
        logger.info("Shutting down ADK CLI application...")
        if self.runner and self.runner.session_service:
            logger.info("Attempting to finalize session service...")
            # We don't know the exact method to call for saving.
            # If SqliteSessionService has a close() or dispose() method,
            # it would ideally be called here.
            # For now, we'll just log that we're in the shutdown process.
            # Example: if hasattr(self.runner.session_service, 'close'):
            #             await self.runner.session_service.close()
            # Or: if hasattr(self.runner.session_service, 'dispose'):
            #         await self.runner.session_service.dispose()
            logger.info(
                "Session service finalize attempt complete (or no specific method found)."
            )
        else:
            logger.info("No runner or session service found for shutdown cleanup.")


if __name__ == "__main__":
    app = AdkTuiApp()
    app.run()
