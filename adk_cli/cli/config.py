import click
import json
from adk_cli.settings import load_settings, load_global_settings, save_settings
from adk_cli.projects import find_project_root


@click.group()
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


@config.command(name="set")
@click.argument("key")
@click.argument("value")
def set_config_cmd(key: str, value: str) -> None:
    """Set a global configuration value.

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
