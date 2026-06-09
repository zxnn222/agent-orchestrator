"""Demo 3: Complete workflow - LLM decomposition, parallel agents, self-adaptation."""
import asyncio, logging, os, sys
from datetime import date

CODEX = [
    r"C:\Program Files\nodejs\node.exe",
    os.path.join(os.environ["APPDATA"],
        "npm", "node_modules", "@openai", "codex", "bin", "codex.js"),
]
sys.path.insert(0, os.path.dirname(__file__))
from agent_orchestrator import Orchestrator
from agent_orchestrator.adapters.codex_cli import CodexCLIAdapter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def status_callback(event, data):
    if event == "tasks_decomposed":
        print(f"[📋] Decomposed into {data['count']} tasks:")
        for t in data["tasks"]:
            print(f"      · {t[:60]}")
    elif event in ("task_completed", "task_started"):
        pass
    elif event == "completed":
        print(f"[🏁] Done: {data['completed']}/{data['total']} succeeded")

async def main():
    adapter = CodexCLIAdapter(codex_binary=CODEX)
    o = Orchestrator(adapter, max_concurrent_agents=3, auto_retry=True, max_retries=1)
    o.on_status(status_callback)
    print("=" * 55)
    print("  Agent Orchestrator - Complete Workflow Demo")
    print("=" * 55)
    goal = ("Create a project report: list files, count lines of code,"
            " save result as report.md in current directory.")
    print(f"  Goal: {goal[:60]}...")
    print()
    results = await o.run(goal)
    print()
    print("-" * 55)
    for t in results:
        mark = "[OK]" if t.status.name == "COMPLETED" else "[FAIL]"
        print(f"  {mark} [{t.id[:6]}] {t.title[:55]}")
    print(f"  Total: {len(results)} tasks")
    print("=" * 55)

asyncio.run(main())