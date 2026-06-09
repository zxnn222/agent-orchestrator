from __future__ import annotations
import asyncio, json, logging
from .task import Task, TaskStatus
from .workflow import WorkflowEngine

logger = logging.getLogger(__name__)

class Orchestrator:
    """Self-orchestrating multi-agent system.

    Takes a high-level goal, decomposes it into sub-tasks using Codex LLM,
    dynamically creates agents for each task, executes them in DAG order,
    and self-adapts on failure until completion.
    """

    def __init__(self, adapter, max_concurrent_agents=3,
                 auto_retry=True, max_retries=2):
        self.adapter = adapter
        self.workflow = WorkflowEngine()
        self.max_concurrent = max_concurrent_agents
        self.auto_retry = auto_retry
        self.max_retries = max_retries
        self._on_status = None

    def on_status(self, callback):
        self._on_status = callback

    async def run(self, goal, context=None):
        """Main entry point. Returns list of completed tasks."""
        logger.info(f"Starting: {goal[:80]}...")
        await self._emit("initializing", {"goal": goal})

        await self.adapter.initialize()
        await self._emit("adapter_ready", {})

        top = Task(title=goal, description=goal, context=context or {})
        top = await self._decompose(top)
        await self._emit("tasks_decomposed", {
            "count": len(top.sub_tasks),
            "tasks": [t.title for t in top.sub_tasks],
        })

        results = await self._adapt_loop(top.sub_tasks, goal)
        await self.adapter.shutdown()
        await self._emit("completed", {
            "total": len(results),
            "completed": sum(1 for t in results if t.status == TaskStatus.COMPLETED),
            "failed": sum(1 for t in results if t.status == TaskStatus.FAILED),
        })
        return results

    async def _decompose(self, task):
        """Use Codex LLM to break a task into sub-tasks."""
        if hasattr(self.adapter, "decompose"):
            subs = await self.adapter.decompose(task.title)
        else:
            subs = self._simple_decompose(task.title)

        try:
            for s in subs:
                sub = task.add_subtask(s["title"], s.get("description", ""))
                deps = s.get("dependencies", [])
                if deps:
                    resolved = []
                    for d in deps:
                        for t2 in task.sub_tasks:
                            if t2.title == d and t2.id != sub.id:
                                resolved.append(t2.id)
                    sub.dependencies = resolved
            logger.info(f"Decomposed into {len(task.sub_tasks)} sub-tasks")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Decompose failed ({e}), using single task")
            task.add_subtask(title=task.title, description=task.description)
        return task

    def _simple_decompose(self, goal):
        """Simple fallback when adapter has no decompose."""
        return [{"title": "Main Task", "description": goal, "dependencies": []}]

    async def _adapt_loop(self, tasks, goal):
        """Self-adapting execution loop with retry/re-decompose."""
        iteration = 0
        current = list(tasks)
        all_done = []

        while True:
            iteration += 1
            logger.info(f"Iteration {iteration}: {len(current)} tasks")
            await self._emit("iteration",
                {"iteration": iteration, "tasks": len(current)})
            completed = await self.workflow.execute_workflow(
                current, self._exec_one, max_concurrent=self.max_concurrent)
            all_done.extend(completed)

            failed = self.workflow.get_failed(completed)
            if not failed:
                break
            if not self.auto_retry or iteration > self.max_retries + 1:
                logger.warning(f"Giving up on {len(failed)} failed tasks")
                break

            logger.info(f"Retrying {len(failed)} failed tasks...")
            current = []
            for t in failed:
                nt = Task(title=t.title,
                    description=f"{t.description}\nLast error: {t.result}")
                await self._decompose(nt)
                current.extend(nt.sub_tasks or [nt])
        return all_done

    async def _exec_one(self, task):
        """Execute one task via an agent."""
        await self._emit("task_started",
            {"id": task.id, "title": task.title})
        agent_id = await self.adapter.create_agent(task)
        await self.adapter.send_task(agent_id, task)
        await self._emit("task_completed",
            {"id": task.id, "status": task.status.name})
        return task

    async def _emit(self, event, data):
        if self._on_status:
            try:
                cb = self._on_status
                await cb(event, data) if asyncio.iscoroutinefunction(cb) else cb(event, data)
            except Exception:
                pass