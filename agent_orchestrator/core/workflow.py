from __future__ import annotations
import asyncio
import logging
from .task import Task, TaskStatus

logger = logging.getLogger(__name__)

class WorkflowEngine:
    """DAG-based task execution engine."""

    def get_ready_tasks(self, tasks):
        """Get tasks whose dependencies are completed."""
        done_ids = {t.id for t in tasks if t.status == TaskStatus.COMPLETED}
        return [t for t in tasks if t.status == TaskStatus.PENDING
                and all(d in done_ids for d in t.dependencies)]

    def all_done(self, tasks):
        """All tasks in terminal state?"""
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)
                   for t in tasks)

    def get_failed(self, tasks):
        return [t for t in tasks if t.status == TaskStatus.FAILED]

    async def execute_workflow(self, tasks, execute_fn, max_concurrent=3):
        """Execute tasks respecting dependencies."""
        sem = asyncio.Semaphore(max_concurrent)

        async def run_task(task):
            async with sem:
                task.status = TaskStatus.IN_PROGRESS
                try:
                    result = await execute_fn(task)
                    if result.status == TaskStatus.COMPLETED:
                        logger.info(f'OK task: {task.title}')
                    else:
                        logger.warning(f'FAIL: {task.title}')
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.result = str(e)
                    logger.error(f'ERROR: {task.title}: {e}')

        pending = list(tasks)
        in_flight = set()

        while not self.all_done(pending) or in_flight:
            for task in self.get_ready_tasks(pending):
                if task.id not in in_flight:
                    in_flight.add(task.id)
                    asyncio.create_task(run_task(task))
            await asyncio.sleep(0.5)
            done_ids = {t.id for t in pending
                       if t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED)}
            in_flight -= done_ids

        return pending
