"""Start the Agent Orchestrator Dashboard.
Listens on 0.0.0.0 for wider compatibility (in-app browser, Docker, LAN).
"""
import asyncio, logging, os, sys, socket

CODEX = [
    r"C:\Program Files\nodejs\node.exe",
    os.path.join(os.environ["APPDATA"],
        "npm", "node_modules", "@openai", "codex", "bin", "codex.js"),
]

sys.path.insert(0, os.path.dirname(__file__))
from agent_orchestrator.adapters.codex_cli import CodexCLIAdapter
from agent_orchestrator.dashboard import DashboardServer

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("start")


def _get_local_ip() -> str:
    """Get the machine LAN IP for browser access."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


async def main():
    try:
        adapter = CodexCLIAdapter(codex_binary=CODEX)
        dashboard = DashboardServer(
            adapter=adapter,
            host="0.0.0.0",       # bind all interfaces
            port=8765,
            max_concurrent_agents=2,
            auto_retry=True,
            max_retries=1,
        )
        local_ip = _get_local_ip()
        print()
        print("=" * 50)
        print("  Agent Orchestrator Dashboard")
        print(f"  http://localhost:8765")
        print(f"  http://{local_ip}:8765")
        print("=" * 50)
        print()
        logger.info(f"Dashboard starting on 0.0.0.0:8765")
        await dashboard.start()
    except Exception as e:
        logger.error(f"Failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
