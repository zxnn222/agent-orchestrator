"""Unit tests for agent-orchestrator core."""
import pytest, json, asyncio
from agent_orchestrator.core.task import Task, TaskStatus
from agent_orchestrator.core.workflow import WorkflowEngine
from agent_orchestrator.core.orchestrator import Orchestrator


class TestTask:
    def test_creation(self):
        t = Task(title="test", description="desc")
        assert t.status == TaskStatus.PENDING
        assert len(t.id) == 8

    def test_subtask(self):
        p = Task(title="parent")
        c = p.add_subtask("child", "child task")
        assert c.parent_id == p.id
        assert len(p.sub_tasks) == 1
        assert p.sub_tasks[0].title == "child"

    def test_to_dict(self):
        t = Task(title="x", description="y")
        d = t.to_dict()
        assert d["title"] == "x"
        assert d["status"] == "PENDING"

    def test_chain(self):
        """Multiple subtasks with dependencies."""
        root = Task(title="root")
        a = root.add_subtask("A", "Do A")
        b = root.add_subtask("B", "Do B", dependencies=[a.id])
        c = root.add_subtask("C", "Do C", dependencies=[a.id])
        d = root.add_subtask("D", "Do D", dependencies=[b.id, c.id])
        assert len(root.sub_tasks) == 4
        assert d.dependencies == [b.id, c.id]


class TestWorkflow:
    @pytest.mark.asyncio
    async def test_ready_tasks(self):
        w = WorkflowEngine()
        t1 = Task(title="t1")
        t2 = Task(title="t2", dependencies=[t1.id])
        ready = w.get_ready_tasks([t1, t2])
        assert t1 in ready
        assert t2 not in ready
        t1.status = TaskStatus.COMPLETED
        ready = w.get_ready_tasks([t1, t2])
        assert t2 in ready

    @pytest.mark.asyncio
    async def test_all_done(self):
        w = WorkflowEngine()
        t1, t2 = Task(title="a"), Task(title="b")
        assert not w.all_done([t1, t2])
        t1.status = TaskStatus.COMPLETED
        t2.status = TaskStatus.COMPLETED
        assert w.all_done([t1, t2])
        t2.status = TaskStatus.FAILED
        assert w.all_done([t1, t2])

    @pytest.mark.asyncio
    async def test_dag_execution(self):
        """Tasks execute in dependency order."""
        w = WorkflowEngine()
        order = []
        async def exec_fn(t):
            order.append(t.title)
            t.status = TaskStatus.COMPLETED
            return t
        t1 = Task(title="A")
        t2 = Task(title="B", dependencies=[t1.id])
        t3 = Task(title="C", dependencies=[t1.id])
        t4 = Task(title="D", dependencies=[t2.id, t3.id])
        await w.execute_workflow([t1, t2, t3, t4], exec_fn)
        assert order[0] == "A"  # t1 first
        assert order[-1] == "D"  # t4 last
        # t2 and t3 can be in any order after t1
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Independent tasks run in parallel."""
        w = WorkflowEngine()
        started = set()
        sem = asyncio.Semaphore(2)
        async def exec_fn(t):
            async with sem:
                started.add(t.title)
                await asyncio.sleep(0.1)
            t.status = TaskStatus.COMPLETED
            return t
        tasks = [Task(title=f"T{i}") for i in range(4)]
        await w.execute_workflow(tasks, exec_fn, max_concurrent=2)
        assert all(t.status == TaskStatus.COMPLETED for t in tasks)

    @pytest.mark.asyncio
    async def test_task_failure(self):
        """Failed task does not block other parallel tasks."""
        w = WorkflowEngine()
        async def exec_fn(t):
            if "fail" in t.title:
                raise ValueError("intentional")
            t.status = TaskStatus.COMPLETED
            return t
        t1 = Task(title="ok")
        t2 = Task(title="fail1")
        done = await w.execute_workflow([t1, t2], exec_fn)
        assert t1.status == TaskStatus.COMPLETED
        assert t2.status == TaskStatus.FAILED


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_simple_decompose(self):
        """Fallback decompose creates one task."""
        o = Orchestrator(adapter=None)
        task = Task(title="test goal")
        result = await o._decompose(task)
        assert len(result.sub_tasks) == 1
        assert result.sub_tasks[0].title == "Main Task"

    @pytest.mark.asyncio
    async def test_adapt_loop_no_retry(self):
        """Without auto_retry, fails stop immediately."""
        o = Orchestrator(adapter=None, auto_retry=False)
        tasks = [Task(title="t1")]
        tasks[0].status = TaskStatus.FAILED
        result = await o._adapt_loop(tasks, "goal")
        assert len(result) == 1
        assert result[0].status == TaskStatus.FAILED


class TestCodexCLIAdapter:
    def test_import(self):
        from agent_orchestrator.adapters.codex_cli import CodexCLIAdapter
        a = CodexCLIAdapter(codex_binary="echo")
        assert a.binary == ['echo']

    def test_import_appserver(self):
        from agent_orchestrator.adapters.codex_app_server import CodexAppServerAdapter
        a = CodexAppServerAdapter(codex_binary=["echo"])
        assert a.binary == ["echo"]
