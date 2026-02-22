import logging
import asyncio
import json
from typing import Optional, Dict, Any
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
)
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.reactive import reactive
from rich.markdown import Markdown
from google.adk.runners import Runner
from google.genai import types

from rich.syntax import Syntax

from adk_cli.confirmation import confirmation_manager
from adk_cli.status import status_manager
from adk_cli.summarize import summarize_tool_call, summarize_tool_result

logger = logging.getLogger(__name__)


class ConfirmationModal(ModalScreen[bool]):
    """A modal dialog to confirm or deny an action."""

    CSS = """
    ConfirmationModal {
        align: center middle;
    }

    #dialog {
        padding: 1 2;
        width: 80;
        max-height: 80vh;
        border: thick $primary;
        background: $surface;
    }

    #title {
        text-align: center;
        width: 100%;
        text-style: bold;
        margin-bottom: 1;
    }

    #hint {
        margin: 1 0;
        color: $text;
        text-align: center;
    }

    #tool-info {
        margin: 1 0;
        padding: 1;
        background: $boost;
        border: solid $primary;
    }

    #args-container {
        margin: 1 0;
        height: auto;
        max-height: 20;
        border: solid $panel;
    }

    #buttons {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    Button {
        margin: 0 2;
    }
    """

    def __init__(
        self,
        hint: str,
        tool_name: Optional[str] = None,
        tool_args: Optional[Dict[str, Any]] = None,
    ):
        super().__init__()
        self.hint = hint
        self.tool_name = tool_name
        self.tool_args = tool_args

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("⚠️  Confirmation Required", id="title")
            yield Label(self.hint, id="hint")

            if self.tool_name:
                with Vertical(id="tool-info"):
                    summary = summarize_tool_call(self.tool_name, self.tool_args or {})
                    yield Label(f"🛠️ [bold]{summary}[/bold]")

                    if self.tool_args:
                        args_json = json.dumps(self.tool_args, indent=2)
                        lines = args_json.splitlines()
                        if len(lines) > 20:
                            args_json = (
                                "\n".join(lines[:20]) + "\n... (args truncated) ..."
                            )
                        yield Container(
                            Static(Syntax(args_json, "json", theme="monokai")),
                            id="args-container",
                        )

            with Horizontal(id="buttons"):
                yield Button("Approve", variant="success", id="approve")
                yield Button("Deny", variant="error", id="deny")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.dismiss(True)
        else:
            self.dismiss(False)


class Message(Static):
    """A widget to display a chat message."""

    # layout=False (default) avoids an expensive full layout pass on every token.
    text = reactive("")
    thought = reactive("")

    def __init__(self, text: str, role: str, thought: str = ""):
        super().__init__()
        self.role = role
        self._streaming = False
        self.text = text
        self.thought = thought
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
            return f"💭 {self.text}"
        if self.role == "tool":
            return f"🛠️  [bold]{self.text}[/bold]"
        prefix = "🤖 Agent" if self.role == "agent" else "👤 You"

        content = ""
        if self.thought:
            # We use a blockquote-like style for thinking
            content += f"> [italic]{self.thought}[/italic]\n\n"
        content += self.text

        return Markdown(f"### {prefix}\n\n{content}")

    def watch_text(self, old_text: str, new_text: str) -> None:
        """Trigger a refresh when the text changes."""
        if self._streaming:
            # Skip markdown parsing while tokens are streaming in — just show
            # plain text so we avoid O(n) re-parsing on every token delta.
            prefix = "🤖 Agent" if self.role == "agent" else "👤 You"
            content = ""
            if self.thought:
                content += f"(Thinking: {self.thought})\n\n"
            content += new_text
            self.update(f"{prefix}\n\n{content}")
        else:
            self.update(self._markdown_renderable())

    def watch_thought(self, old_thought: str, new_thought: str) -> None:
        """Trigger a refresh when the thought changes."""
        if self._streaming:
            prefix = "🤖 Agent" if self.role == "agent" else "👤 You"
            self.update(f"{prefix}\n\n(Thinking: {new_thought})\n\n{self.text}")
        else:
            self.update(self._markdown_renderable())

    def render(self) -> Markdown:
        return self._markdown_renderable()


class ChatScreen(Screen):
    """The main chat interface screen."""

    CSS = """
    Screen {
        background: #121212;
    }

    #chat-scroll {
        height: 1fr;
        overflow-y: auto;
        padding: 0 1;
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
        color: #888;
        margin: 1 0;
        width: auto;
        padding: 0;
    }

    Message {
        margin: 1 0;
        padding: 1;
        background: #1a1a1a;
    }

    Message.agent {
        border-left: solid #007acc;
    }

    Message.user {
        border-left: solid #28a745;
        background: #1e1e1e;
    }

    Message.status {
        margin: 0 4;
        padding: 0 1;
        background: transparent;
        color: #ffa500;
        border-left: none;
        opacity: 0.8;
    }

    Message.tool {
        margin: 0 4;
        padding: 0 1;
        background: transparent;
        color: #007acc;
        border-left: none;
        opacity: 0.9;
    }

    LoadingIndicator {
        height: 1;
        margin: 1 4;
        color: $primary;
    }
    """

    BINDINGS = [Binding("ctrl+c", "app.quit", "Quit", show=False)]

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

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            with Vertical(id="chat-area"):
                with Horizontal(id="status-bar"):
                    yield Label(f"Project: [bold]{self.user_id}[/]", id="project-label")
                    yield Label(
                        f"Session: [bold]{self.session_id}[/]", id="session-label"
                    )
                with Container(id="chat-scroll"):
                    yield Message(
                        "Welcome to **ADK CLI**! How can I help you today?\n\n"
                        "Type `/quit` or press **Ctrl+C** to exit.",
                        role="agent",
                    )
                with Horizontal(id="input-container"):
                    yield Label("> ")
                    yield Input(
                        placeholder="Ask anything... (or /quit to exit)",
                        id="user-input",
                    )
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#user-input", Input).focus()
        await self.load_history()
        if self.initial_query:
            self.run_worker(self.handle_initial_query(self.initial_query))

    async def load_history(self) -> None:
        """Loads and displays history for the current session."""
        if not self.runner or not self.runner.session_service:
            return

        try:
            session = await self.runner.session_service.get_session(
                app_name="adk-cli", user_id=self.user_id, session_id=self.session_id
            )
            if not session or not session.events:
                return

            chat_scroll = self.query_one("#chat-scroll", Container)

            for event in session.events:
                role = "user" if event.author == "user" else "agent"
                if not event.content or not event.content.parts:
                    continue

                text_parts = []
                for part in event.content.parts:
                    if part.text:
                        text_parts.append(part.text)

                text = "".join(text_parts).strip()
                if text:
                    msg = Message(text, role=role)
                    await chat_scroll.mount(msg)

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
        chat_scroll = self.query_one("#chat-scroll", Container)
        chat_scroll.mount(msg)
        chat_scroll.scroll_end()

    async def process_query(self, query: str) -> None:
        if not self.runner:
            return

        logger.debug(f"--- [Query Processing Started] --- Query: {query}")
        chat_scroll = self.query_one("#chat-scroll", Container)
        await chat_scroll.mount(Message(query, role="user"))
        chat_scroll.scroll_end()

        indicator = LoadingIndicator()
        await chat_scroll.mount(indicator)
        chat_scroll.scroll_end()

        # Input text content specifically from the agent/model
        current_agent_message = None
        # Keep track of tool call arguments so we can summarize the results correctly
        pending_args: Dict[Optional[str], Dict[str, Any]] = {}

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

                            if current_agent_message is None:
                                logger.debug("Initializing new agent message bubble")
                                current_agent_message = Message("", role="agent")
                                current_agent_message.start_streaming()
                                # Mount before the indicator to keep indicator at the bottom
                                await chat_scroll.mount(
                                    current_agent_message, before=indicator
                                )

                            if part_thought:
                                current_agent_message.thought += part_thought
                            if part_text:
                                current_agent_message.text += part_text

                        if part.function_response:
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

                                await chat_scroll.mount(
                                    Message(f"✅ {summary}", role="status"),
                                    before=indicator,
                                )
                                chat_scroll.scroll_end()
                    # Scroll once per event, not per individual text part.
                    if current_agent_message is not None:
                        chat_scroll.scroll_end()

                if event.get_function_calls():
                    # If we have an active agent message, "close" it to ensure the tool call
                    # is mounted AFTER the text, and later text is mounted AFTER the tool call.
                    if current_agent_message:
                        logger.debug(
                            "Closing current agent message bubble before tool call"
                        )
                        current_agent_message.finish_streaming()
                        current_agent_message = None

                    for call in event.get_function_calls():
                        logger.debug(f"Requesting function call execution: {call.name}")

                        # Store arguments for later result summarization
                        call_name = call.name or "unknown"
                        pending_args[call_name] = call.args or {}

                        # ADK emits an internal confirmation function call when
                        # tool_context.request_confirmation() is used. Since the
                        # ConfirmationModal already provides the UI for this interaction,
                        # skip the generic "🛠️ Executing:" bubble for these calls to
                        # avoid showing a confusing duplicate/internal message.
                        if call.name == "adk_request_confirmation":
                            logger.debug(
                                f"Skipping display of ADK confirmation call: {call.name}"
                            )
                            continue

                        # Use a more descriptive tool display
                        display_name: str = summarize_tool_call(
                            call_name, call.args or {}
                        )

                        await chat_scroll.mount(
                            Message(display_name, role="tool"), before=indicator
                        )
                        chat_scroll.scroll_end()

            logger.debug("--- [Query Finished Successfully] ---")
            # Finalise the last agent message bubble with a proper markdown render.
            if current_agent_message is not None:
                current_agent_message.finish_streaming()
            # Final scroll to ensure everything is visible after all mount events settle
            chat_scroll.scroll_end()
        except Exception as e:
            logger.exception("Error during runner execution:")
            await chat_scroll.mount(
                Message(f"❌ Error: {str(e)}", role="agent"), before=indicator
            )
            chat_scroll.scroll_end()
        finally:
            await indicator.remove()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        if text.lower() == "/quit":
            self.app.exit()
            return

        self.query_one("#user-input", Input).value = ""
        self.run_worker(self.process_query(text))


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
        Displays a modal to ask for user confirmation.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        # ModalScreen.dismiss calls the callback passed to push_screen
        self.push_screen(
            ConfirmationModal(hint, tool_name, tool_args), callback=future.set_result
        )
        return await future


if __name__ == "__main__":
    app = AdkTuiApp()
    app.run()
