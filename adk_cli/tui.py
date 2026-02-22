from typing import Optional
from textual.app import App, ComposeResult, Screen
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Static, Label
from textual.binding import Binding
from rich.markdown import Markdown
from google.adk.runners import Runner
from google.genai import types


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

    async def process_query(self, query: str) -> None:
        if not self.runner:
            return

        chat_scroll = self.query_one("#chat-scroll", Container)
        await chat_scroll.mount(Message(query, role="user"))
        chat_scroll.scroll_end()

        agent_message = Message("", role="agent")
        await chat_scroll.mount(agent_message)
        chat_scroll.scroll_end()

        new_message = types.Content(role="user", parts=[types.Part(text=query)])

        try:
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=self.session_id,
                new_message=new_message,
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if part.text:
                            agent_message.text += part.text
                            agent_message.refresh()
                            chat_scroll.scroll_end()

                if event.get_function_calls():
                    for call in event.get_function_calls():
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

        except Exception as e:
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

    def on_mount(self) -> None:
        self.push_screen(
            ChatScreen(
                runner=self.runner,
                user_id=self.user_id,
                session_id=self.session_id,
                initial_query=self.initial_query,
            )
        )


if __name__ == "__main__":
    app = AdkTuiApp()
    app.run()
