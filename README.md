# Agent Orchestrator

**Self-orchestrating multi-agent system powered by Codex CLI.**

每个任务自己拆解和编排，自动生成所需的 agent，每个 agent 只处理一件事，
自循环，自适配，直到整个任务跑完。

## Quick Start

```bash
pip install agent-orchestrator
```

## How It Works

```
Your Goal → Orchestrator → Codex LLM decomposes into sub-tasks
                             ↓
                   ┌── Agent 1 (Codex exec) → Task A ──┐
                   │   Agent 2 (Codex exec) → Task B ──┤── DAG Engine
                   │   Agent 3 (Codex exec) → Task C ──┘
                             ↓
                   Fail? → Re-decompose & retry
                   Done? → Collect results
```

## Features

- **LLM Task Decomposition** — Uses Codex itself to break goals into sub-tasks via structured prompts
- **DAG Execution Engine** — Independent tasks run in parallel, dependent tasks wait automatically
- **Self-Adaptation** — Failed tasks are re-decomposed into simpler sub-tasks and retried
- **Codex exec Integration** — Uses `codex exec` (non-interactive mode) with sandbox control
- **Status Callbacks** — Real-time event stream for monitoring progress
- **Plugin Architecture** — Adapter pattern supports multiple backends (Codex CLI, App Server, etc.)

## Usage

```python
import asyncio
from agent_orchestrator import Orchestrator
from agent_orchestrator.adapters.codex_cli import CodexCLIAdapter

async def main():
    adapter = CodexCLIAdapter(codex_binary="codex")
    orchestrator = Orchestrator(adapter, max_concurrent_agents=2)

    def status(event, data):
        print(f"[{event}] {data}")
    orchestrator.on_status(status)

    results = await orchestrator.run("Create a Python web scraper")
    for t in results:
        print(f"{t.status.name}: {t.title}")

asyncio.run(main())
```

## Architecture

```
agent_orchestrator/
├── core/
│   ├── orchestrator.py    # Main controller: decompose → execute → adapt
│   ├── task.py             # Task/TaskStatus models
│   └── workflow.py         # DAG execution engine (dependency resolution)
├── adapters/
│   ├── base.py             # AgentAdapter abstract interface
│   ├── codex_cli.py        # Codex CLI subprocess adapter (+ decompose)
│   └── codex_app_server.py # Codex Desktop JSON-RPC adapter
└── tests/
    └── test_core.py        # Unit tests
```

## Requirements

- Python ≥ 3.10
- [Codex CLI](https://github.com/openai/codex) (`npm install -g @openai/codex`)

## License MIT