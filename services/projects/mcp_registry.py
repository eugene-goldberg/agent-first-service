"""Tool registry for the Projects MCP server.

The tool registry maps each tool name (as derived by
``agent_protocol.mcp_adapter.capability_to_tool``) to the 5-tuple
``ToolRegistryEntry`` describing how the adapter should dispatch an
MCP ``tools/call`` invocation into the wrapped Projects FastAPI app.

Both the stdio/SSE ``mcp_server.build_projects_mcp_server`` factory and the
adapter-level unit tests import ``build_tool_registry`` from here so there is
exactly one source of truth for the Projects service's tool surface.
"""

from __future__ import annotations

from agent_protocol.mcp_adapter import ToolRegistryEntry
from services.projects.models import CreateProject, CreateTask, UpdateProject, UpdateTask


def build_tool_registry() -> dict[str, ToolRegistryEntry]:
    """Return the full tool_registry for the Projects service.

    Keys match the tool names derived by ``capability_to_tool`` for the eight
    entries in ``services.projects.routes.capabilities._CAPABILITIES``.
    """

    return {
        "get_projects": ("/projects", "GET", None, [], []),
        "post_projects": ("/projects", "POST", CreateProject, [], []),
        "get_projects_id": ("/projects/{project_id}", "GET", None, ["project_id"], []),
        "patch_projects_id": (
            "/projects/{project_id}",
            "PATCH",
            # PATCH /projects/{project_id} accepts sparse updates for
            # name/description, so MCP should advertise both as optional.
            UpdateProject,
            ["project_id"],
            [],
        ),
        "get_projects_id_tasks": (
            "/projects/{project_id}/tasks",
            "GET",
            None,
            ["project_id"],
            [],
        ),
        "post_projects_id_tasks": (
            "/projects/{project_id}/tasks",
            "POST",
            CreateTask,
            ["project_id"],
            [],
        ),
        "patch_tasks_id": (
            "/tasks/{task_id}",
            "PATCH",
            UpdateTask,
            ["task_id"],
            [],
        ),
        "get_tasks_assignee_id_status_status_milestone_id": (
            "/tasks",
            "GET",
            None,
            [],
            ["assignee", "status", "milestone"],
        ),
    }
