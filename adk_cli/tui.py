from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Static, Label
from textual.binding import Binding
from rich.markdown import Markdown
from typing import Optional
from google.adk.runners import Runner


class Message(Static):
    """A widget to display a chat message."""

    def __init__(self, text: str, role: str):
        super().__init__()
        self.text = text
        self.role = role
        self.add_class(role)

    def render(self) -> Markdown:
        prefix = "🤖 Agent" if self.role == "agent" else "👤 You"
        return Markdown(f"### {prefix}\n\n{self.text}")


class AdkTuiApp(App):
    """The main TUI for adk-cli."""

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
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
    ]

    def __init__(
        self, initial_query: Optional[str] = None, runner: Optional[Runner] = None
    ):
        super().__init__()
        self.initial_query = initial_query
        self.runner = runner

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            with Vertical(id="chat-area"):
                with Container(id="chat-scroll"):
                    yield Message(
                        "Welcome to **ADK CLI**! How can I help you today?",
                        role="agent",
                    )
                with Horizontal(id="input-container"):
                    yield Label("> ")
                    yield Input(placeholder="Ask anything...", id="user-input")
        yield Footer()

    async def on_mount(self) -> None:
        self.query_one("#user-input", Input).focus()
        if self.initial_query:
            # We can't easily wait for the app to be fully ready to process
            # but we can schedule it or just call the logic.
            # Using post_message or just calling the handler
            self.run_worker(self.handle_initial_query(self.initial_query))

    async def handle_initial_query(self, query: str) -> None:
        # Simulate submission logic
        chat_scroll = self.query_one("#chat-scroll", Container)
        await chat_scroll.mount(Message(query, role="user"))
        chat_scroll.scroll_end()
        await chat_scroll.mount(
            Message(f"I received your initial query: {query}", role="agent")
        )
        chat_scroll.scroll_end()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if not event.value.strip():
            return

        user_text = event.value
        self.query_one("#user-input", Input).value = ""

        # Add user message to UI
        chat_scroll = self.query_one("#chat-scroll", Container)
        await chat_scroll.mount(Message(user_text, role="user"))
        chat_scroll.scroll_end()

        # TODO: Trigger ADK Agent execution
        # For now, just echo back
        await chat_scroll.mount(Message(f"I received: {user_text}", role="agent"))
        chat_scroll.scroll_end()


if __name__ == "__main__":
    app = AdkTuiApp()
    app.run()
