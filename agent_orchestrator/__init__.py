"""
agent-orchestrator - Self-orchestrating multi-agent system.
Powered by Codex CLI - each task gets its own agent, self-decomposing & self-adapting.
"""
from .core.orchestrator import Orchestrator
from .core.task import Task, TaskStatus
from .adapters.codex_app_server import CodexAppServerAdapter
from .adapters.codex_cli import CodexCLIAdapter
from .adapters.shell import ShellAdapter
__all__ = [
    "Orchestrator", "Task", "TaskStatus",
    "CodexCLIAdapter", "CodexAppServerAdapter", "ShellAdapter",
]
