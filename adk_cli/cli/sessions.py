import click
import asyncio
from datetime import datetime
from adk_cli.projects import find_project_root, get_project_id, get_session_db_path
from adk_cli.constants import APP_NAME


@click.group()
def sessions() -> None:
    """Manage agent sessions."""
    pass


@sessions.command(name="list")
@click.option("--all", is_flag=True, help="List sessions across all projects.")
def list_sessions_cmd(all: bool) -> None:
    """List recent sessions."""
    from google.adk.sessions.sqlite_session_service import SqliteSessionService

    db_path = str(get_session_db_path())
    service = SqliteSessionService(db_path=db_path)

    project_root = find_project_root()
    project_id = get_project_id(project_root)

    async def _list():
        response = await service.list_sessions(
            app_name=APP_NAME, user_id=None if all else project_id
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
    from google.adk.sessions.sqlite_session_service import SqliteSessionService

    db_path = str(get_session_db_path())
    service = SqliteSessionService(db_path=db_path)

    project_root = find_project_root()
    project_id = get_project_id(project_root)

    async def _delete():
        await service.delete_session(
            app_name=APP_NAME, user_id=project_id, session_id=session_id
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
    from google.adk.sessions.sqlite_session_service import SqliteSessionService

    db_path = str(get_session_db_path())
    service = SqliteSessionService(db_path=db_path)

    async def _gc():
        response = await service.list_sessions(app_name=APP_NAME)
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
                app_name=APP_NAME, user_id=s.user_id, session_id=s.id
            )

        click.echo(f"Successfully deleted {len(to_delete)} sessions.")

    asyncio.run(_gc())
