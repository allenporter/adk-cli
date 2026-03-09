import os
import sys
import logging
from pathlib import Path
from typing import Any, Optional

import click

from google.adk.agents.llm_agent import LlmAgent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.planners import BuiltInPlanner
from google.adk.runners import Runner
from google.adk.sessions.sqlite_session_service import SqliteSessionService
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.adk.tools.skill_toolset import SkillToolset
from google.genai import types

from adk_coder.api_key import load_api_key, load_env_file
from adk_coder.constants import APP_NAME, DEFAULT_MODEL
from adk_coder.policy import CustomPolicyEngine, PermissionMode, SecurityPlugin
from adk_coder.projects import find_project_root, get_session_db_path
from adk_coder.retry_gemini import AdkRetryGemini
from adk_coder.settings import load_settings
from adk_coder.skills import discover_skills
from adk_coder.tools import get_essential_tools
from adk_coder.mcp import get_mcp_toolsets

logger = logging.getLogger(__name__)


SUPERVISOR_INSTRUCTION = """\
You are an expert AI software engineer and the primary supervisor for this adk-coder session.
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

  adk-coder will load this file automatically on startup.

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
    agent_name: str = "adk_coder_agent",
    workspace_path: Path | None = None,
    extra_tools: list[BaseTool | BaseToolset] | None = None,
) -> LlmAgent:
    """Builds and returns an LlmAgent for adk-coder.

    Args:
        model: Optional model name. If not provided, loads from settings or uses default.
        instruction: Optional system instruction. If not provided, uses `SUPERVISOR_INSTRUCTION`.
        tool_names: Optional list of tool names to include. Filters built-in tools.
        include_skills: Whether to discover and include skills from the workspace.
        agent_name: Name of the agent.
        workspace_path: Optional path to the workspace root. If not provided,
            project root is discovered from ``Path.cwd()``.
        extra_tools: Additional tools to provide to the agent.
            This can include manually instantiated ``McpToolset`` objects.
    """
    # Ensure agent_name is a valid identifier (alphanumeric and underscores only)
    agent_name = agent_name.replace("-", "_")

    project_root = find_project_root(workspace_path)

    # Defer loading of model settings
    if model is None:
        settings = load_settings(project_root)
        model = settings.get("default_model") or DEFAULT_MODEL

    # Load project-specific instructions if available
    project_instructions = []
    instruction_markers = ["AGENTS.md", "GEMINI.md", "CLAUDE.md"]
    for marker in instruction_markers:
        marker_path = project_root / marker
        if marker_path.exists():
            try:
                project_instructions.append(
                    f"\n--- From {marker} ---\n"
                    + marker_path.read_text(encoding="utf-8")
                )
            except Exception as e:
                logger.warning("Failed to read %s: %s", marker, e)

    final_instruction = instruction or SUPERVISOR_INSTRUCTION
    if project_instructions:
        final_instruction += "\n\n## Project-Specific Instructions\n" + "\n".join(
            project_instructions
        )

    retry_options = types.HttpRetryOptions(attempts=1, http_status_codes=[])
    llm_model = AdkRetryGemini(model=model, retry_options=retry_options)

    # Collect and filter tools
    all_essential_tools = get_essential_tools()
    if tool_names:
        tools = [t for t in all_essential_tools if getattr(t, "name", "") in tool_names]
    else:
        tools = all_essential_tools

    if include_skills:
        skills = discover_skills(workspace_path or Path.cwd())
        if skills:
            tools.append(SkillToolset(skills))

    # Load MCP servers from config (checking both mcpServers and legacy mcp_servers)
    settings = load_settings(project_root)
    tools.extend(get_mcp_toolsets(settings))

    if extra_tools:
        tools.extend(extra_tools)

    # Construct the planner with thinking config
    planner = BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
            thinking_budget=1024 if agent_name == "adk_coder_agent" else 512,
        )
    )

    # Initialize the LlmAgent directly
    return LlmAgent(
        name=agent_name,
        instruction=final_instruction,
        tools=tools,
        model=llm_model,
        planner=planner,
    )


def build_runner(
    model: str | None = None,
    instruction: str | None = None,
    tool_names: list[str] | None = None,
    include_skills: bool = True,
    agent_name: str = "adk_coder_agent",
    permission_mode: str = "ask",
    workspace_path: Path | None = None,
    extra_tools: list[BaseTool | BaseToolset] | None = None,
) -> Runner:
    """Build a fully-configured Runner (agent + sessions + compaction).

    This is the library-friendly entry point with no CLI dependencies
    (click, sys.exit). adk-claw and other consumers should use this.

    Args:
        workspace_path: Optional path to the workspace root. Forwarded to
            ``build_adk_agent()`` for project root and skill discovery.
    """
    agent = build_adk_agent(
        model=model,
        instruction=instruction,
        tool_names=tool_names,
        include_skills=include_skills,
        agent_name=agent_name,
        workspace_path=workspace_path,
        extra_tools=extra_tools,
    )
    mode = PermissionMode(permission_mode)

    policy_engine = CustomPolicyEngine(mode=mode)
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


def build_runner_or_exit(ctx: click.Context, model: str | None = None) -> Any:
    """CLI wrapper — resolves API key or exits, then delegates to build_runner()."""
    api_key = _resolve_api_key()
    if not api_key:
        click.echo(_NO_KEY_MESSAGE, err=True)
        sys.exit(1)
    # Set env var so google-genai client picks it up at init time
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")

    # Resolve permission mode from CLI context, then fall back to settings
    p_params = ctx.parent.params if ctx.parent else {}
    mode = p_params.get("permission_mode")
    if mode is None:
        settings = load_settings(find_project_root())
        mode = settings.get("permission_mode", "ask")

    return build_runner(model=model, permission_mode=mode)
