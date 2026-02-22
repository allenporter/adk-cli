import sys
import click
import asyncio
import uuid
from typing import Optional, List, Any, Dict
import logging

from adk_cli.projects import find_project_root, get_project_id, get_session_db_path
from adk_cli.status import is_session_locked, SessionLock
from adk_cli.summarize import summarize_tool_call, summarize_tool_result
from adk_cli.cli.sessions import sessions
from adk_cli.cli.config import config
from adk_cli.constants import APP_NAME

logger = logging.getLogger(__name__)


class DefaultGroup(click.Group):
    """A Click group that invokes a default command if no subcommand is matched."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.default_command = kwargs.pop("default_command", None)
        super().__init__(*args, **kwargs)

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, Optional[click.Command], list[str]]:
        try:
            cmd_name, cmd, args = super().resolve_command(ctx, args)
            if cmd_name is None and self.default_command:
                return super().resolve_command(ctx, [self.default_command] + args)
            return cmd_name, cmd, args
        except click.UsageError:
            if self.default_command:
                new_args = [self.default_command] + args
                return super().resolve_command(ctx, new_args)
            raise


def setup_logging(verbose: bool) -> None:
    """Configures logging for adk-cli."""
    level = logging.DEBUG if verbose else logging.WARNING
    log_file = "adk-cli.log"
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=log_file,
        filemode="a",
    )
    logging.getLogger("markdown_it").setLevel(logging.WARNING)
    if verbose:
        logger.info("Logging initialized at DEBUG level.")


async def _get_project_context(
    new_session: bool, resume_session_id: Optional[str]
) -> tuple[str, str]:
    """
    Returns the project ID (user_id) and session ID.
    By default, finds the most recent session for the project.
    """
    project_root = find_project_root()
    project_id = get_project_id(project_root)

    if resume_session_id:
        return project_id, resume_session_id

    if not new_session:
        from google.adk.sessions.sqlite_session_service import SqliteSessionService

        db_path = str(get_session_db_path())
        service = SqliteSessionService(db_path=db_path)
        try:
            response = await service.list_sessions(
                app_name=APP_NAME, user_id=project_id
            )
            if response.sessions:
                # Sort by last_update_time descending
                sorted_sessions = sorted(
                    response.sessions, key=lambda s: s.last_update_time, reverse=True
                )
                candidate_id = sorted_sessions[0].id
                if not is_session_locked(candidate_id):
                    return project_id, candidate_id
        except Exception as e:
            logger.warning(f"Failed to list sessions for continuation: {e}")

    return project_id, str(uuid.uuid4())[:8]


@click.group(cls=DefaultGroup, default_command="chat", invoke_without_command=True)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable debug logging to a file 'adk-cli.log'.",
)
@click.option(
    "--print",
    "-p",
    "print_mode",
    is_flag=True,
    help="Print Mode: Executes a task and outputs result to stdout without a TUI.",
)
@click.option(
    "--new",
    "-n",
    "new_session",
    is_flag=True,
    help="Starts a new session (ignores history).",
)
@click.option(
    "--resume",
    "-r",
    "resume_session_id",
    help="Resumes a specific session ID.",
)
@click.option("--add-dir", multiple=True, help="Include additional directories.")
@click.option("--model", help="Switch between specific Gemini models.")
@click.option("--max-turns", type=int, help="Cap the number of tool execution loops.")
@click.option("--max-budget-usd", type=float, help="Safety cap on session costs.")
@click.option("--system-prompt", help="Replace the base instructions.")
@click.option("--append-system-prompt", help="Add context-specific rules.")
@click.option(
    "--permission-mode",
    type=click.Choice(["plan", "auto", "ask"]),
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
    verbose: bool,
    print_mode: bool,
    new_session: bool,
    resume_session_id: Optional[str],
    add_dir: List[str],
    model: Optional[str],
    max_turns: Optional[int],
    max_budget_usd: Optional[float],
    system_prompt: Optional[str],
    append_system_prompt: Optional[str],
    permission_mode: Optional[str],
    output_format: str,
) -> None:
    """adk-cli: A powerful agentic CLI built with google-adk."""
    setup_logging(verbose)
    if ctx.invoked_subcommand is None:
        ctx.invoke(chat)


@cli.command()
@click.argument("query", nargs=-1)
@click.option("--print", "-p", "print_mode", is_flag=True)
@click.pass_context
def chat(ctx: click.Context, query: List[str], print_mode: bool) -> None:
    """Execute a task or start a conversation."""
    from google.genai import types
    from adk_cli.tui import AdkTuiApp
    from adk_cli.agent_factory import build_runner_or_exit

    query_str = " ".join(query)
    is_print = print_mode
    # Consistently use print mode if the parent group has it
    if ctx.parent and ctx.parent.params.get("print_mode"):
        is_print = True

    parent_params = ctx.parent.params if ctx.parent else {}
    new_sess = parent_params.get("new_session", False)
    resume_id = parent_params.get("resume_session_id")

    # Resolve project and session context
    project_id, session_id = asyncio.run(_get_project_context(new_sess, resume_id))

    if is_print:
        runner = build_runner_or_exit(ctx)
        with SessionLock(session_id):
            click.echo(
                f"Executing one-off query (Project: {project_id}, Session: {session_id})"
            )
            logger.debug(f"Executing one-off query in print mode: {query_str}")
            new_message = types.Content(role="user", parts=[types.Part(text=query_str)])
            # Keep track of tool call arguments so we can summarize the results correctly
            pending_args: Dict[Optional[str], Dict[str, Any]] = {}

            for event in runner.run(
                user_id=project_id, session_id=session_id, new_message=new_message
            ):
                if event.content and event.content.parts:
                    role = event.content.role
                    for part in event.content.parts:
                        if not part.function_call and not part.function_response:
                            part_text = getattr(part, "text", None)
                            if part.thought:
                                if part_text and isinstance(part_text, str):
                                    click.echo(f"\n[Thinking: {part_text.strip()}]")
                            elif part_text and isinstance(part_text, str):
                                if role != "user":
                                    click.echo(part_text, nl=False)

                        if part.function_response:
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
                                click.echo(f"\n✅ {summary}")
                if event.get_function_calls():
                    for call in event.get_function_calls():
                        logger.debug(
                            f"Sync Requesting function call execution: {call.name}"
                        )

                        # Store arguments for later result summarization
                        call_name = call.name or "unknown"
                        pending_args[call_name] = call.args or {}

                        if call.name == "adk_request_confirmation":
                            logger.debug(
                                f"Skipping display of ADK confirmation call: {call.name}"
                            )
                            continue

                        summary = summarize_tool_call(call_name, call.args or {})
                        click.echo(f"\n🛠️ {summary}")
        logger.debug("--- [CLI One-off query finished] ---")
        click.echo()
    else:
        runner = build_runner_or_exit(ctx)
        with SessionLock(session_id):
            app = AdkTuiApp(
                initial_query=query_str,
                runner=runner,
                user_id=project_id,
                session_id=session_id,
            )
            app.run()


@cli.command()
def agents() -> None:
    """Lists and manages active sub-agents and skills."""
    click.echo("Listing agents and skills...")


@cli.command()
def mcp() -> None:
    """Manages Model Context Protocol server connections."""
    click.echo("Managing MCP connections...")


cli.add_command(sessions)
cli.add_command(config)


def main(args: Optional[List[str]] = None) -> None:
    if args is None:
        args = sys.argv[1:]
    cli(args=args)


if __name__ == "__main__":
    main()
