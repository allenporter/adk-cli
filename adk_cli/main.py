import os
import sys
import json
import click
import asyncio
import uuid
from click import Command
from typing import Optional, List, Any
import logging
from pathlib import Path
from datetime import datetime

from google.genai import types
from google.adk.runners import Runner
from google.adk.agents.llm_agent import LlmAgent
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk.tools.skill_toolset import SkillToolset
from google.adk.apps.app import App, EventsCompactionConfig

from adk_cli.policy import SecurityPlugin, CustomPolicyEngine, PermissionMode
from adk_cli.retry_gemini import AdkRetryGemini
from adk_cli.tui import AdkTuiApp
from adk_cli.tools import get_essential_tools
from adk_cli.api_key import load_api_key, load_env_file
from adk_cli.skills import discover_skills
from adk_cli.projects import find_project_root, get_project_id, get_session_db_path
from adk_cli.status import is_session_locked, SessionLock
from adk_cli.settings import load_settings, load_global_settings, save_settings

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3-flash-preview"


_NO_KEY_MESSAGE = """\
Error: No Gemini API key found.

To get started:
  1. Get a free API key from https://aistudio.google.com/apikey
  2. Create a .env file in your project directory with:

       GOOGLE_API_KEY="YOUR_API_KEY"
       GOOGLE_GENAI_USE_VERTEXAI=FALSE

  adk-cli will load this file automatically on startup.

  See: https://google.github.io/adk-docs/agents/models/google-gemini/#google-ai-studio
"""


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
                new_args = [self.default_command] + args
                return super().resolve_command(ctx, new_args)
            raise


def setup_logging(verbose: bool) -> None:
    """Configures logging for adk-cli."""
    level = logging.DEBUG if verbose else logging.WARNING
    # In TUI, we don't want logs to stdout. Instead, log to a file.
    log_file = "adk-cli.log"
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=log_file,
        filemode="a",
    )
    # Suppress noisy external libraries even in verbose mode
    logging.getLogger("markdown_it").setLevel(logging.WARNING)
    if verbose:
        logger.info("Logging initialized at DEBUG level.")


async def _get_project_context(
    new_session: bool, resume_session_id: Optional[str]
) -> tuple[str, str]:
    """
    Returns the project ID (user_id) and session ID.
    By default, finds the most recent session for the project.
    If new_session is True, creates a new session ID.
    """
    project_root = find_project_root()
    project_id = get_project_id(project_root)

    if resume_session_id:
        return project_id, resume_session_id

    if not new_session:
        db_path = str(get_session_db_path())
        service = SqliteSessionService(db_path=db_path)
        try:
            response = await service.list_sessions(
                app_name="adk-cli", user_id=project_id
            )
            if response.sessions:
                # Sort by last_update_time descending
                sorted_sessions = sorted(
                    response.sessions, key=lambda s: s.last_update_time, reverse=True
                )
                candidate_id = sorted_sessions[0].id

                # If the most recent session is locked, don't resume it unless forced
                if is_session_locked(candidate_id):
                    logger.info(
                        f"Session {candidate_id} is locked. Starting a new session."
                    )
                else:
                    return project_id, candidate_id
        except Exception as e:
            logger.warning(f"Failed to list sessions for continuation: {e}")

    # Default: create a new unique session ID if starting fresh
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
    permission_mode: str,
    output_format: str,
) -> None:
    """adk-cli: A powerful agentic CLI built with google-adk."""
    setup_logging(verbose)
    if ctx.invoked_subcommand is None:
        project_id, session_id = asyncio.run(
            _get_project_context(new_session, resume_session_id)
        )

        runner = _build_runner_or_exit(ctx, model)
        with SessionLock(session_id):
            app = AdkTuiApp(runner=runner, user_id=project_id, session_id=session_id)
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

    parent_params = ctx.parent.params if ctx.parent else {}
    new_session = parent_params.get("new_session", False)
    resume_session_id = parent_params.get("resume_session_id")

    # Resolve project and session context
    project_id, session_id = asyncio.run(
        _get_project_context(new_session, resume_session_id)
    )

    if is_print:
        runner = _build_runner_or_exit(ctx)
        with SessionLock(session_id):
            click.echo(
                f"Executing one-off query (Project: {project_id}, Session: {session_id})"
            )
            logger.debug(f"Executing one-off query in print mode: {query_str}")
            new_message = types.Content(role="user", parts=[types.Part(text=query_str)])
            for event in runner.run(
                user_id=project_id, session_id=session_id, new_message=new_message
            ):
                logger.debug(f"Received sync Runner event type: {type(event)}")
                if event.content and event.content.parts:
                    role = event.content.role
                    for part in event.content.parts:
                        if part.text and role != "user":
                            click.echo(part.text, nl=False)
                if event.get_function_calls():
                    for call in event.get_function_calls():
                        logger.debug(
                            f"Sync Requesting function call execution: {call.name}"
                        )
                        if call.name == "adk_request_confirmation":
                            logger.debug(
                                f"Skipping display of ADK confirmation call: {call.name}"
                            )
                            continue
                        args = call.args or {}
                        args_str = (
                            ", ".join(f"{k}={v!r}" for k, v in args.items())
                            if isinstance(args, dict)
                            else str(args)
                        )
                        click.echo(f"\n🛠️ Executing: {call.name}({args_str})")
        logger.debug("--- [CLI One-off query finished] ---")
        click.echo()
    else:
        runner = _build_runner_or_exit(ctx)
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


@cli.group()
def sessions() -> None:
    """Manage agent sessions."""
    pass


@cli.group()
def config() -> None:
    """Manage global settings."""
    pass


@config.command(name="list")
def list_config_cmd() -> None:
    """List effective configurations.

    Shows a merged view where local project settings override global tool settings.
    """
    settings = load_settings(find_project_root())
    if not settings:
        click.echo("No settings found.")
        return
    for k, v in settings.items():
        click.echo(f"{k}: {v}")


@config.command(name="get")
@click.argument("key")
def get_config_cmd(key: str) -> None:
    """Get the effective configuration for the given key."""
    settings = load_settings(find_project_root())
    if key in settings:
        click.echo(settings[key])
    else:
        click.echo(f"Key '{key}' not found.")


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def set_config_cmd(key: str, value: str) -> None:
    """Set a global tool configuration.

    The change is saved to ~/.adk/settings.json. Project-level overrides
    must be managed via manual file edits or environment variables.
    """
    settings = load_global_settings()
    # Try to parse as JSON if it looks like it, otherwise keep as string
    try:
        parsed_value = json.loads(value)
    except Exception:
        parsed_value = value
    settings[key] = parsed_value
    save_settings(settings)
    click.echo(f"Set global {key} to {value}")


@sessions.command(name="list")
@click.option("--all", is_flag=True, help="List sessions across all projects.")
def list_sessions_cmd(all: bool) -> None:
    """List recent sessions."""
    db_path = str(get_session_db_path())
    service = SqliteSessionService(db_path=db_path)

    project_root = find_project_root()
    project_id = get_project_id(project_root)

    async def _list():
        response = await service.list_sessions(
            app_name="adk-cli", user_id=None if all else project_id
        )
        if not response.sessions:
            click.echo("No sessions found.")
            return

        # Sort by last_update_time descending
        sorted_sessions = sorted(
            response.sessions, key=lambda s: s.last_update_time, reverse=True
        )

        click.echo(f"{'SESSION ID':<15} {'PROJECT':<15} {'UPDATED':<20}")
        click.echo("-" * 50)
        for s in sorted_sessions:
            updated = datetime.fromtimestamp(s.last_update_time).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            click.echo(f"{s.id:<15} {s.user_id:<15} {updated:<20}")

    asyncio.run(_list())


@sessions.command(name="delete")
@click.argument("session_id")
def delete_session_cmd(session_id: str) -> None:
    """Delete a specific session."""
    db_path = str(get_session_db_path())
    service = SqliteSessionService(db_path=db_path)

    project_root = find_project_root()
    project_id = get_project_id(project_root)

    async def _delete():
        await service.delete_session(
            app_name="adk-cli", user_id=project_id, session_id=session_id
        )
        click.echo(f"Session {session_id} deleted.")

    asyncio.run(_delete())


@sessions.command(name="gc")
@click.option(
    "--days", type=int, default=30, help="Delete sessions older than this many days."
)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def gc_sessions_cmd(days: int, yes: bool) -> None:
    """Garbage collect old sessions."""
    db_path = str(get_session_db_path())
    service = SqliteSessionService(db_path=db_path)

    async def _gc():
        response = await service.list_sessions(app_name="adk-cli")
        if not response.sessions:
            click.echo("No sessions found.")
            return

        now = datetime.now().timestamp()
        threshold = now - (days * 24 * 60 * 60)

        to_delete = [s for s in response.sessions if s.last_update_time < threshold]

        if not to_delete:
            click.echo(f"No sessions older than {days} days found.")
            return

        click.echo(
            f"Found {len(to_delete)} sessions to delete (older than {days} days)."
        )

        if not yes:
            if not click.confirm("Do you want to proceed?"):
                click.echo("Aborted.")
                return

        for s in to_delete:
            await service.delete_session(
                app_name="adk-cli", user_id=s.user_id, session_id=s.id
            )

        click.echo(f"Successfully deleted {len(to_delete)} sessions.")

    asyncio.run(_gc())


def main(args: Optional[List[str]] = None) -> None:
    if args is None:
        args = sys.argv[1:]
    cli(args=args)


def _resolve_api_key() -> Optional[str]:
    """Load .env then return the API key, or None."""
    load_env_file(workspace_dir=os.getcwd())
    return load_api_key()


def build_adk_agent(model: str | None = None) -> LlmAgent:
    """Builds and returns the main LlmAgent for adk-cli."""
    # Discover skills and inject into instructions
    skills = discover_skills(Path.cwd())
    if skills:
        logger.debug("Loaded %d skill(s): %s", len(skills), [s.name for s in skills])

    tools: list[Any] = get_essential_tools()
    if skills:
        tools.append(SkillToolset(skills))

    # Build the agent
    retry_options = types.HttpRetryOptions(
        attempts=1,  # Our custom wrapper handles the retries
        http_status_codes=[],
    )

    if model is None:
        settings = load_settings(find_project_root())
        model = settings.get("default_model")

    llm_model = AdkRetryGemini(
        model=model or DEFAULT_MODEL, retry_options=retry_options
    )

    return LlmAgent(
        name="adk_cli_agent",
        model=llm_model,
        tools=tools,
    )


def _build_runner_or_exit(ctx: click.Context, model: str | None = None) -> Runner:
    """Resolve the API key and build a Runner, or print instructions and exit."""
    api_key = _resolve_api_key()
    if not api_key:
        click.echo(_NO_KEY_MESSAGE, err=True)
        sys.exit(1)
    # Set env var so google-genai client picks it up at init time
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

    # Create the agent lazily after api key setup
    agent = build_adk_agent(model)

    settings = load_settings(find_project_root())

    mode_str = ctx.parent.params.get("permission_mode") if ctx.parent else None
    if mode_str is None:
        mode_str = settings.get("permission_mode", "ask")

    permission_mode = PermissionMode(mode_str)

    policy_engine = CustomPolicyEngine(mode=permission_mode)
    security_plugin = SecurityPlugin(policy_engine=policy_engine)

    # Configure session compaction to manage context growth.
    # We use a combination of sliding window and token-based compaction.
    compaction_config = EventsCompactionConfig(
        compaction_interval=5,  # Compact every 5 turns
        overlap_size=1,  # Keep 1 turn of overlap for continuity
        token_threshold=50000,  # Also compact if we hit 50k tokens
        event_retention_size=10,  # Keep at least 10 raw events
    )

    app = App(
        name="adk_cli",
        root_agent=agent,
        plugins=[security_plugin],
        events_compaction_config=compaction_config,
    )

    db_path = str(get_session_db_path())
    session_service = SqliteSessionService(db_path=db_path)

    return Runner(
        app=app,
        session_service=session_service,
        auto_create_session=True,
    )


if __name__ == "__main__":
    main()
