"""M3 只读工具白名单。模型只能看到这里显式注册的能力。"""

from app.agent.tools.base import ToolPermission
from app.agent.tools.notes import get_note_tool, lint_knowledge_tool, search_notes_tool
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.tasks import get_task_tool, list_tasks_tool

READ_TOOL_REGISTRY = ToolRegistry(
    [
        search_notes_tool,
        get_note_tool,
        list_tasks_tool,
        get_task_tool,
        lint_knowledge_tool,
    ],
    allowed_permissions={ToolPermission.READ},
)
READ_TOOL_REGISTRY.freeze()

__all__ = ["READ_TOOL_REGISTRY"]
