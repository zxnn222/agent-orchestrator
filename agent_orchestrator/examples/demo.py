"""
Usage examples for agent-orchestrator.

Run: python -m agent_orchestrator.examples.demo
"""
import asyncio
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from agent_orchestrator import Orchestrator, CodexAppServerAdapter, CodexCLIAdapter

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


async def demo_app_server():
    """Demo using Codex Desktop app-server."""
    print("\n" + "="*50)
    print("Demo 1: Codex App-Server Orchestration")
    print("="*50)

    adapter = CodexAppServerAdapter(codex_binary='codex', model='gpt-5.4-codex')
    orchestrator = Orchestrator(adapter, max_concurrent_agents=2)

    def status(event, data):
        emoji = {'initializing': chr(0x1F3AF), 'task_started': chr(0x1F680),
                 'task_completed': chr(0x2705), 'completed': chr(0x1F3C1)}
        print(f'  {emoji.get(event, chr(0x1F4CC))} [{event}] {data}')
    orchestrator.on_status(status)

    goal = "Create a simple hello.py that prints Hello World"
    print(f'Goal: {goal}')
    results = await orchestrator.run(goal)
    print(f'Done: {len(results)} tasks')
    for t in results:
        icon = chr(0x2705) if t.status.name == 'COMPLETED' else chr(0x274C)
        print(f'  {icon} {t.title[:60]}')


async def demo_cli():
    """Demo using standalone Codex CLI."""
    print("\n" + "="*50)
    print("Demo 2: Codex CLI Orchestration")
    print("="*50)

    adapter = CodexCLIAdapter(codex_binary='codex',
                              base_dir='E:/agentTEAM/agent-orchestrator-worktrees')
    orchestrator = Orchestrator(adapter, max_concurrent_agents=1, auto_retry=False)
    results = await orchestrator.run('Print hello world in Python')
    for t in results:
        icon = chr(0x2705) if t.status.name == 'COMPLETED' else chr(0x274C)
        print(f'  {icon} {t.title[:60]}')


async def main():
    print('='*50)
    print('Agent Orchestrator Demo')
    print("="*50)
    try:
        await demo_app_server()
    except Exception as e:
        print(f'App-server failed: {e}')
        try:
            await demo_cli()
        except Exception as e2:
            print(f'CLI also failed: {e2}')
            print('Install Codex CLI: npm install -g codex')


if __name__ == "__main__":
    asyncio.run(main())