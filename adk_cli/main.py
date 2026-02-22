import click
from click import Command
import sys
from typing import Optional, List, Any
from google.genai import types

from google.adk.runners import Runner
from google.adk.agents.llm_agent import LlmAgent
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from adk_cli.policy import SecurityPlugin, CustomPolicyEngine, PermissionMode
from adk_cli.tui import AdkTuiApp
from adk_cli.tools import get_essential_tools

DEFAULT_MODEL = "gemini-3.0-flash-preview"


class DefaultGroup(click.Group):
    """A Click group that invokes a default command if no subcommand is matched."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.default_command = kwargs.pop("default_command", None)
        super().__init__(*args, **kwargs)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, Command | None, list[str]]:
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if self.default_command:
                # Insert the default command name at the beginning of args
                new_args = [self.default_command] + args
                return super().resolve_command(ctx, new_args)
            raise


@click.group(cls=DefaultGroup, default_command="chat", invoke_without_command=True)
@click.option(
    "--print",
    "-p",
    "print_mode",
    is_flag=True,
    help="Print Mode: Executes a task and outputs result to stdout without a TUI.",
)
@click.option(
    "--continue",
    "-c",
    "continue_session",
    is_flag=True,
    help="Resumes the most recent session.",
)
@click.option(
    "--resume",
    "-r",
    "resume_session_id",
    help="Resumes a specific named or ID-based session.",
)
@click.option(
    "--add-dir",
    multiple=True,
    help="Include additional directories in the working set.",
)
@click.option("--model", help="Switch between specific Gemini models.")
@click.option("--max-turns", type=int, help="Cap the number of tool execution loops.")
@click.option("--max-budget-usd", type=float, help="Safety cap on session costs.")
@click.option(
    "--system-prompt", help="Replace the base instructions (text or file path)."
)
@click.option(
    "--append-system-prompt", help="Add context-specific rules (text or file path)."
)
@click.option(
    "--permission-mode",
    type=click.Choice(["plan", "auto", "ask"]),
    default="ask",
    help="Permission mode for tool execution.",
)
@click.option(
    "--output-format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def cli(
    ctx: click.Context,
    print_mode: bool,
    continue_session: bool,
    resume_session_id: Optional[str],
    add_dir: List[str],
    model: Optional[str],
    max_turns: Optional[int],
    max_budget_usd: Optional[float],
    system_prompt: Optional[str],
    append_system_prompt: Optional[str],
    permission_mode: str,
    output_format: str,
) -> None:
    """adk-cli: A powerful agentic CLI built with google-adk."""
    if ctx.invoked_subcommand is None:
        session_id = resume_session_id or "default_session"
        if continue_session:
            # Logic to find the most recent session could go here
            session_id = "default_session"

        runner = _get_runner(ctx)
        app = AdkTuiApp(runner=runner, session_id=session_id)
        app.run()


@cli.command()
@click.argument("query", nargs=-1)
@click.option("--print", "-p", "print_mode", is_flag=True)
@click.pass_context
def chat(ctx: click.Context, query: List[str], print_mode: bool) -> None:
    """Execute a task or start a conversation."""
    query_str = " ".join(query)
    is_print = print_mode
    if ctx.parent and ctx.parent.params.get("print_mode"):
        is_print = True

    session_id = "default_session"
    if ctx.parent:
        if parent_session_id := ctx.parent.params.get("resume_session_id"):
            session_id = str(parent_session_id)
        elif ctx.parent.params.get("continue_session"):
            session_id = "default_session"  # Should be most recent

    if is_print:
        click.echo(f"Executing one-off query in print mode: {query_str}")
        runner = _get_runner(ctx)

        new_message = types.Content(role="user", parts=[types.Part(text=query_str)])

        for event in runner.run(
            user_id="default_user", session_id=session_id, new_message=new_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        click.echo(part.text, nl=False)
            if event.get_function_calls():
                for call in event.get_function_calls():
                    click.echo(f"\n🛠️ Executing: {call.name}")
        click.echo()  # Newline at the end
    else:
        runner = _get_runner(ctx)
        app = AdkTuiApp(initial_query=query_str, runner=runner, session_id=session_id)
        app.run()


@cli.command()
def agents() -> None:
    """Lists and manages active sub-agents and skills."""
    click.echo("Listing agents and skills...")


@cli.command()
def mcp() -> None:
    """Manages Model Context Protocol server connections."""
    click.echo("Managing MCP connections...")


def main(args: Optional[List[str]] = None) -> None:
    if args is None:
        args = sys.argv[1:]

    cli(args=args)


def _get_runner(ctx: click.Context) -> Runner:
    """Helper to initialize the ADK Runner with policy engine and plugins."""
    mode_str = ctx.parent.params.get("permission_mode", "ask") if ctx.parent else "ask"
    permission_mode = PermissionMode(mode_str)

    policy_engine = CustomPolicyEngine(mode=permission_mode)
    security_plugin = SecurityPlugin(policy_engine=policy_engine)

    # Basic agent setup
    agent = LlmAgent(
        name="adk_cli_agent",
        model=DEFAULT_MODEL,
        tools=get_essential_tools(),
    )

    return Runner(
        app_name="adk-cli",
        agent=agent,
        session_service=InMemorySessionService(),  # type: ignore[no-untyped-call]
        plugins=[security_plugin],
        auto_create_session=True,
    )


if __name__ == "__main__":
    main()
