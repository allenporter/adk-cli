import os
import sys
import logging
from pathlib import Path
from typing import Any, Optional

import click

from adk_cli.api_key import load_api_key, load_env_file
from adk_cli.projects import find_project_root, get_session_db_path
from adk_cli.settings import load_settings
from adk_cli.constants import APP_NAME, DEFAULT_MODEL

logger = logging.getLogger(__name__)


SUPERVISOR_INSTRUCTION = """\
You are an expert AI software engineer and the primary supervisor for this adk-cli session.
Your goal is to help the user manage, explore, and modify their codebase efficiently and safely.

Guidelines:
- **Think First**: Use your internal reasoning (BuiltInPlanner) to plan your actions.
- **Use Specialized Skills**: For complex tasks like feature development, architecture changes, or deep exploration, prefer using the relevant 'Skill' (e.g., `feature-dev`).
- **Safety**: Always ask for confirmation before executing potentially destructive shell commands (via `bash`) or making large-scale file edits.
- **Precision**: When editing files, ensure you have read the relevant sections first to maintain project style and logic.
"""

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


def _resolve_api_key() -> Optional[str]:
    """Load .env then return the API key, or None."""
    load_env_file(workspace_dir=os.getcwd())
    return load_api_key()


def build_adk_agent(
    model: str | None = None,
    instruction: str | None = None,
    tool_names: list[str] | None = None,
    include_skills: bool = True,
    agent_name: str = "adk_cli_agent",
) -> Any:
    """Builds and returns an LlmAgent for adk-cli."""
    from adk_cli.skills import discover_skills
    from adk_cli.tools import get_essential_tools
    from adk_cli.retry_gemini import AdkRetryGemini
    from google.adk.agents.llm_agent import LlmAgent
    from google.adk.tools.skill_toolset import SkillToolset
    from google.genai import types

    # Ensure agent_name is a valid identifier (alphanumeric and underscores only)
    agent_name = agent_name.replace("-", "_")

    # Defer loading of model settings
    if model is None:
        settings = load_settings(find_project_root())
        model = settings.get("default_model") or DEFAULT_MODEL

    retry_options = types.HttpRetryOptions(attempts=1, http_status_codes=[])
    llm_model = AdkRetryGemini(model=model, retry_options=retry_options)

    # Collect and filter tools
    all_essential_tools = get_essential_tools()
    if tool_names:
        tools = [t for t in all_essential_tools if getattr(t, "name", "") in tool_names]
    else:
        tools = all_essential_tools

    if include_skills:
        skills = discover_skills(Path.cwd())
        if skills:
            tools.append(SkillToolset(skills))

    # Construct the planner with thinking config
    from google.adk.planners import BuiltInPlanner

    planner = BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024 if agent_name == "adk_cli_agent" else 512,
        )
    )

    # Initialize the LlmAgent directly
    return LlmAgent(
        name=agent_name,
        instruction=instruction or SUPERVISOR_INSTRUCTION,
        tools=tools,
        model=llm_model,
        planner=planner,
    )


def build_runner_or_exit(ctx: click.Context, model: str | None = None) -> Any:
    """Resolve the API key and build a Runner, or print instructions and exit."""
    # Defer loading of heavy SDK libraries
    from adk_cli.policy import CustomPolicyEngine, SecurityPlugin, PermissionMode
    from google.adk.apps.app import App, EventsCompactionConfig
    from google.adk.runners import Runner
    from google.adk.sessions.sqlite_session_service import SqliteSessionService

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

    # Navigate to get parent context params if needed
    p_params = ctx.parent.params if ctx.parent else {}
    mode_str = p_params.get("permission_mode")
    if mode_str is None:
        mode_str = settings.get("permission_mode", "ask")

    permission_mode = PermissionMode(mode_str)

    policy_engine = CustomPolicyEngine(mode=permission_mode)
    security_plugin = SecurityPlugin(policy_engine=policy_engine)

    # Configure session compaction to manage context growth.
    compaction_config = EventsCompactionConfig(
        compaction_interval=5,  # Compact every 5 turns
        overlap_size=1,  # Keep 1 turn of overlap for continuity
        token_threshold=50000,  # Also compact if we hit 50k tokens
        event_retention_size=10,  # Keep at least 10 raw events
    )

    app = App(
        name=APP_NAME,
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
