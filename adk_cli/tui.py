import logging
import asyncio
from typing import Optional
from textual.app import App, ComposeResult, Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Static, Label, Button
from textual.binding import Binding
from textual.screen import ModalScreen
from rich.markdown import Markdown
from google.adk.runners import Runner
from google.genai import types

from adk_cli.confirmation import confirmation_manager
from adk_cli.status import status_manager

logger = logging.getLogger(__name__)


class ConfirmationModal(ModalScreen[bool]):
    """A modal dialog to confirm or deny an action."""

    CSS = """
    ConfirmationModal {
        align: center middle;
    }

    #dialog {
        padding: 1 2;
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
    }

    #hint {
        margin: 1 0;
        color: $text;
        text-align: center;
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

    def __init__(self, hint: str):
        super().__init__()
        self.hint = hint

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("⚠️  Confirmation Required", id="title")
            yield Label(self.hint, id="hint")
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

    def __init__(self, text: str, role: str):
        super().__init__()
        self.text = text
        self.role = role
        self.add_class(role)

    def render(self) -> Markdown:
        if self.role == "status":
            return Markdown(f"*💭 {self.text}*")

        prefix = "🤖 Agent" if self.role == "agent" else "👤 You"
        return Markdown(f"### {prefix}\n\n{self.text}")


class ChatScreen(Screen):
    """The main chat interface screen."""

    CSS = """
    Screen {
        background: #121212;
    }

    #chat-scroll {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }

    #input-container {
        height: auto;
        border-top: solid #333;
        padding: 1;
    }

    Input {
        border: none;
        background: #1e1e1e;
    }

    Label {
        color: #888;
        padding: 0 1;
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
    }

    Message.status {
        background: #221100;
        color: #ffa500;
        border-left: solid #ffa500;
        opacity: 0.8;
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
        if self.initial_query:
            self.run_worker(self.handle_initial_query(self.initial_query))

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

        # Input text content specifically from the agent/model
        current_agent_message = None

        new_message = types.Content(role="user", parts=[types.Part(text=query)])

        try:
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=new_message,
            ):
                logger.debug(f"Received Runner event: {event}")
                if event.content and event.content.parts:
                    # Filter for model-originated text ONLY to avoid dumping tool outputs/user text
                    role = event.content.role
                    for part in event.content.parts:
                        if part.text and role == "model":
                            if current_agent_message is None:
                                current_agent_message = Message("", role="agent")
                                await chat_scroll.mount(current_agent_message)

                            current_agent_message.text += part.text
                            current_agent_message.refresh()
                            chat_scroll.scroll_end()

                if event.get_function_calls():
                    # If we have an active agent message, "close" it to ensure the tool call
                    # is mounted AFTER the text, and later text is mounted AFTER the tool call.
                    current_agent_message = None
                    for call in event.get_function_calls():
                        logger.debug(f"Requesting function call execution: {call.name}")
                        args = call.args or {}
                        args_str = (
                            ", ".join(f"{k}={v!r}" for k, v in args.items())
                            if isinstance(args, dict)
                            else str(args)
                        )
                        await chat_scroll.mount(
                            Message(
                                f"🛠️ Executing: {call.name}({args_str})", role="agent"
                            )
                        )
                        chat_scroll.scroll_end()

            logger.debug("--- [Query Finished Successfully] ---")
        except Exception as e:
            logger.exception("Error during runner execution:")
            await chat_scroll.mount(Message(f"❌ Error: {str(e)}", role="agent"))
            chat_scroll.scroll_end()

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

    async def ask_confirmation(self, req_id: str, hint: str) -> bool:
        """
        Displays a modal to ask for user confirmation.
        """
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        # ModalScreen.dismiss calls the callback passed to push_screen
        self.push_screen(ConfirmationModal(hint), callback=future.set_result)
        return await future


if __name__ == "__main__":
    app = AdkTuiApp()
    app.run()
