from __future__ import annotations
import asyncio, json, logging, os, tempfile
from .base import AgentAdapter
from ..core.task import Task, TaskStatus

logger = logging.getLogger(__name__)

class CodexCLIAdapter(AgentAdapter):
    """Spawns Codex CLI `exec` subprocess per task."""

    def __init__(self, codex_binary="codex", base_dir=None, model=None,
                 sandbox="danger-full-access", extra_dirs=None):
        """Initialize adapter.
        Args:
            codex_binary: Path to codex binary (str) or [node, script] list
        """
        self.binary = codex_binary if isinstance(codex_binary, (list, tuple)) else [codex_binary]
        self.base_dir = base_dir or os.path.join(
            tempfile.gettempdir(), "agent-orchestrator")
        self.model = model
        self.sandbox = sandbox
        self.extra_dirs = extra_dirs or []
        self._agents = {}
        os.makedirs(self.base_dir, exist_ok=True)

    async def initialize(self):
        """Check codex is available."""
        proc = await asyncio.create_subprocess_exec(
            *self.binary, "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"Codex not found: {stderr.decode()}")
        logger.info(f"Codex CLI: {stdout.decode().strip()}")

    async def create_agent(self, task):
        agent_id = f"agent-{task.id}"
        work_dir = os.path.join(self.base_dir, agent_id)
        os.makedirs(work_dir, exist_ok=True)
        self._agents[agent_id] = {"work_dir": work_dir, "task": task}
        task.agent_id = agent_id
        return agent_id

    async def send_task(self, agent_id, task):
        """Run codex exec with task as prompt."""
        agent = self._agents.get(agent_id)
        if not agent: raise ValueError(f"Agent {agent_id} not found")

        agent_dir = agent["work_dir"]
        prompt_path = os.path.join(agent_dir, "prompt.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(f"# {task.title}\n\n{task.description}")

        cmd = list(self.binary) + ["exec",
               "--sandbox", self.sandbox,
               "--skip-git-repo-check",
               "--cd", agent_dir]
        for d in self.extra_dirs:
            cmd.extend(["--add-dir", d])
        if self.model:
            cmd.extend(["--model", self.model])
        cmd.append(prompt_path)

        logger.info(f"Agent {agent_id} starting: {task.title[:50]}")
        proc = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=agent_dir)
        agent["process"] = proc

        stdout, stderr = await proc.communicate()
        out = stdout.decode(errors="replace")
        result_path = os.path.join(agent_dir, "output.md")
        with open(result_path, "w", encoding="utf-8") as f:
            f.write(out)

        task.status = TaskStatus.COMPLETED
        task.result = out[:10000]
        return task.result

    async def get_status(self, agent_id):
        agent = self._agents.get(agent_id) or {}
        proc = agent.get("process")
        if not proc: return "pending"
        if proc.returncode is None: return "running"
        return "completed" if proc.returncode == 0 else "failed"

    async def shutdown(self):
        for a in self._agents.values():
            p = a.get("process")
            if p and p.returncode is None:
                p.terminate()
                try: await asyncio.wait_for(p.wait(), 3)
                except: p.kill()
        logger.info("Agents shut down")

    async def decompose(self, goal):
        """Use codex exec to decompose a goal into sub-tasks."""
        prompt = (
            "Decompose the following goal into clear, independent sub-tasks.\n"
            "\n"
            f"Goal: {goal}\n"
            "\n"
            "Rules:\n"
            "- Each sub-task must be small enough for ONE agent to complete\n"
            "- Sub-tasks can have dependencies on each other\n"
            "- Output ONLY a valid JSON array, no other text\n"
            "- Format: [{\"title\": \"...\", \"description\": \"...\", \"dependencies\": [\"title_of_dep\"]}]\n"
        )
        work_dir = os.path.join(self.base_dir, "decomposer")
        os.makedirs(work_dir, exist_ok=True)
        prompt_path = os.path.join(work_dir, "decompose.md")
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        cmd = list(self.binary) + ["exec",
               "--sandbox", "read-only",
               "--skip-git-repo-check",
               "--cd", work_dir, prompt_path]
        if self.model:
            cmd.extend(["--model", self.model])

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE, cwd=work_dir)
        stdout, stderr = await proc.communicate()
        result = stdout.decode(errors="replace")

        # Extract JSON array from output
        try:
            start = result.index("[")
            end = result.rindex("]") + 1
            json_str = result[start:end]
            return json.loads(json_str)
        except (ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Decompose parse failed: {e}")
            return [{"title": "Main Task", "description": goal, "dependencies": []}]