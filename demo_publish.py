"""Demo 4: Full pipeline - Orchestrate agents, then auto-push to GitHub.
Shows how ShellAdapter solves the git push reliability issue.

Usage:
    python demo_publish.py
"""
import asyncio, logging, os, sys, time

CODEX = [
    r"C:\Program Files\nodejs\node.exe",
    os.path.join(os.environ["APPDATA"],
        "npm", "node_modules", "@openai", "codex", "bin", "codex.js"),
]

sys.path.insert(0, os.path.dirname(__file__))
from agent_orchestrator import Orchestrator, ShellAdapter, CodexCLIAdapter, TaskStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("demo4")

REPO_DIR = os.path.dirname(os.path.abspath(__file__))

# ── helpers ──────────────────────────────────────────────────────────────

def print_header(text):
    print(f"\n{'=' * 55}")
    print(f"  {text}")
    print(f"{'=' * 55}")

def status_cb(event, data):
    if event == "tasks_decomposed":
        print(f"   Decomposed into {data['count']} tasks")
    elif event == "task_completed":
        print(f"   [OK] task {data.get('id','?')[:6]} - {data.get('status','')}")
    elif event == "completed":
        s = data
        print(f"   Done: {s['completed']}/{s['total']} succeeded")

# ── Main ─────────────────────────────────────────────────────────────────

async def main():
    print_header("Demo 4: Auto-Publish to GitHub")
    print(f"  Repo: {REPO_DIR}")
    print()

    # ── Step 1: Generate content with Codex agents ───────────────────────
    print_header("Step 1: Generate project report via Codex CLI agents")
    adapter = CodexCLIAdapter(codex_binary=CODEX)
    orch = Orchestrator(adapter, max_concurrent_agents=2,
                         auto_retry=True, max_retries=1)
    orch.on_status(status_cb)

    goal = (
        "Create a project summary report for this agent-orchestrator project. "
        "List the main modules (core, adapters, dashboard), describe what each does, "
        "count the Python files and total lines of code. "
        "Save the result as PUBLISH_REPORT.md in the current directory."
    )
    results = await orch.run(goal)
    print(f"  Generated {len(results)} task results")

    # ── Step 2: Commit & Push to GitHub using ShellAdapter ───────────────
    print_header("Step 2: Commit and push to GitHub (with retry)")

    # 2a: git add + commit
    print("  [*] git add -A && git commit ...")
    commit_msg = f"Auto-publish by agent-orchestrator @ {time.strftime('%Y-%m-%d %H:%M')}"
    try:
        output = await ShellAdapter.git_add_commit(REPO_DIR, message=commit_msg)
        for line in output.strip().split("\n"):
            if line.strip():
                print(f"       {line.strip()}")
    except Exception as e:
        logger.warning(f"git commit (may be nothing to commit): {e}")

    # 2b: git push with automatic retry (up to 3 attempts)
    print("  [*] git push (with retry up to 3x)...")
    try:
        output = await ShellAdapter.git_push(REPO_DIR, max_retries=3, timeout=60)
        for line in output.strip().split("\n"):
            if line.strip():
                print(f"       {line.strip()}")
        print("  [OK] Pushed to GitHub successfully!")
    except RuntimeError as e:
        print(f"  [FAIL] {e}")
        print("  Tip: Try manual: cd agent-orchestrator-pkg && git push")

    print()
    print_header("Done!")
    print(f"  See: https://github.com/zxnn222/agent-orchestrator")
    print()

if __name__ == "__main__":
    asyncio.run(main())
