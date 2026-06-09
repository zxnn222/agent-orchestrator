"""
ShellAdapter - Direct subprocess execution with retry logic.
No LLM overhead - runs commands directly for reliable operations like git, filesystem.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from .base import AgentAdapter
from ..core.task import Task, TaskStatus

logger = logging.getLogger(__name__)


class ShellAdapter(AgentAdapter):
    """Executes tasks as shell commands directly (no LLM).

    Ideal for: git push, file ops, build, deploy, etc.
    Supports auto-retry with exponential backoff.
    """

    def __init__(self, base_dir: str | None = None,
                 retry_delay_base: float = 2.0,
                 max_retries: int = 3,
                 timeout: int = 120):
        self.base_dir = base_dir or os.path.join(
            tempfile.gettempdir(), "agent-orchestrator-shell")
        self.retry_delay_base = retry_delay_base
        self.max_retries = max_retries
        self.timeout = timeout
        self._agents: dict[str, dict] = {}
        os.makedirs(self.base_dir, exist_ok=True)

    async def initialize(self):
        logger.info("ShellAdapter ready")

    async def create_agent(self, task) -> str:
        agent_id = f"shell-{task.id}"
        work_dir = os.path.join(self.base_dir, agent_id)
        os.makedirs(work_dir, exist_ok=True)
        self._agents[agent_id] = {"work_dir": work_dir, "task": task}
        task.agent_id = agent_id
        return agent_id

    async def send_task(self, agent_id: str, task: Task) -> str:
        """Execute task.description as a shell command with retry."""
        agent = self._agents.get(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")

        command = task.description.strip()
        if not command:
            task.status = TaskStatus.FAILED
            task.result = "Empty command"
            return task.result

        work_dir = agent["work_dir"]
        logger.info(f"[Shell] Executing: {command[:120]}")

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *self._parse_command(command),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=work_dir,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.timeout)
                out = stdout.decode(errors="replace")
                err = stderr.decode(errors="replace")

                if proc.returncode == 0:
                    task.status = TaskStatus.COMPLETED
                    result = (f"Command: {command}\n"
                              f"Exit code: 0\n"
                              f"STDOUT:\n{out[:8000]}")
                    if err:
                        result += f"\nSTDERR:\n{err[:2000]}"
                    task.result = result
                    logger.info(f"[Shell] OK (attempt {attempt}): {command[:60]}")
                    return task.result
                else:
                    last_error = (f"Exit code: {proc.returncode}\n"
                                  f"STDOUT:\n{out[:2000]}\n"
                                  f"STDERR:\n{err[:2000]}")
                    logger.warning(f"[Shell] Failed attempt {attempt}: {command[:60]}")

            except asyncio.TimeoutError:
                last_error = f"Timed out after {self.timeout}s"
                logger.warning(f"[Shell] Timeout attempt {attempt}: {command[:60]}")

            if attempt < self.max_retries:
                delay = self.retry_delay_base * (2 ** (attempt - 1))
                logger.info(f"[Shell] Retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)

        task.status = TaskStatus.FAILED
        task.result = f"All {self.max_retries} attempts failed.\n{last_error}"
        logger.error(f"[Shell] FAILED after {self.max_retries} retries: {command[:60]}")
        return task.result

    async def get_status(self, agent_id: str) -> str:
        return "completed"

    async def shutdown(self):
        self._agents.clear()
        logger.info("ShellAdapter shut down")

    def _parse_command(self, command: str) -> list[str]:
        """Parse a command string into args list, handling quoting."""
        import shlex
        try:
            return shlex.split(command, posix=False)
        except Exception:
            return command.split()

    # --- Convenience: git helpers ---

    @staticmethod
    async def git_push(repo_dir: str | Path,
                       max_retries: int = 3,
                       timeout: int = 60) -> str:
        """Retry-capable git push. Returns stdout."""
        repo_dir = str(repo_dir)
        cmd = ["git", "push"]

        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, cwd=repo_dir)
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout)
                out = stdout.decode(errors="replace")
                err = stderr.decode(errors="replace")

                if proc.returncode == 0:
                    logger.info(f"[git-push] OK (attempt {attempt})")
                    return out
                else:
                    last_error = err or out
                    logger.warning(f"[git-push] Failed attempt {attempt}: "
                                   f"code={proc.returncode}")

            except asyncio.TimeoutError:
                last_error = f"Timed out after {timeout}s"
                logger.warning(f"[git-push] Timeout attempt {attempt}")

            if attempt < max_retries:
                delay = 3.0 * (2 ** (attempt - 1))
                logger.info(f"[git-push] Retrying in {delay:.0f}s...")
                await asyncio.sleep(delay)

        raise RuntimeError(f"git push failed after {max_retries} retries:\n{last_error}")

    @staticmethod
    async def git_add_commit(repo_dir: str | Path,
                             message: str = "Auto-update by agent-orchestrator",
                             timeout: int = 30) -> str:
        """git add -A && git commit. Returns combined stdout."""
        repo_dir = str(repo_dir)
        results = []

        proc = await asyncio.create_subprocess_exec(
            "git", "add", "-A",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=repo_dir)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        results.append(stdout.decode(errors="replace"))

        proc = await asyncio.create_subprocess_exec(
            "git", "commit", "--allow-empty", "-m", message,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=repo_dir)
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        results.append(stdout.decode(errors="replace"))

        return "\n".join(results)

