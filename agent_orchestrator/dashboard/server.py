"""
FastAPI + SSE dashboard for real-time multi-agent monitoring.

Dependencies:
    pip install fastapi uvicorn sse-starlette
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent_orchestrator import Orchestrator

logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

class RunRequest(BaseModel):
    goal: str
    context: Optional[dict] = None


# ---------------------------------------------------------------------------
# Dashboard server
# ---------------------------------------------------------------------------

class DashboardServer:
    """FastAPI + SSE dashboard server.

    Usage::

        dashboard = DashboardServer(adapter, host="0.0.0.0", port=8765)
        await dashboard.start()
    """

    def __init__(
        self,
        adapter,
        host: str = "0.0.0.0",
        port: int = 8765,
        max_concurrent_agents: int = 3,
        auto_retry: bool = True,
        max_retries: int = 2,
    ):
        self.adapter = adapter
        self.host = host
        self.port = port
        self.max_concurrent_agents = max_concurrent_agents
        self.auto_retry = auto_retry
        self.max_retries = max_retries

        # SSE queue: each connected client gets an asyncio.Queue
        self._queues: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._orchestrator: Optional[Orchestrator] = None
        self._server: Optional[uvicorn.Server] = None

        # Build FastAPI app
        self.app = FastAPI(title="Agent Dashboard")
        self._register_routes()

        # Load embedded HTML once
        html_path = HERE / "templates" / "index.html"
        self._html = html_path.read_text(encoding="utf-8")

    # ---- SSE broadcast ---------------------------------------------------

    async def _broadcast(self, event: str, data: dict):
        payload = {"event": event, "data": data}
        async with self._lock:
            for q in self._queues:
                await q.put(payload)

    # ---- Orchestrator status callback ------------------------------------

    async def _on_status(self, event: str, data: dict):
        """Callback installed into Orchestrator -- broadcasts to SSE clients."""
        await self._broadcast(event, data)

    # ---- Run orchestration -----------------------------------------------

    async def _run_orchestration(self, goal: str, context: Optional[dict] = None):
        try:
            orch = Orchestrator(
                adapter=self.adapter,
                max_concurrent_agents=self.max_concurrent_agents,
                auto_retry=self.auto_retry,
                max_retries=self.max_retries,
            )
            orch.on_status(self._on_status)
            self._orchestrator = orch
            await orch.run(goal, context=context)
        except asyncio.CancelledError:
            logger.info("Orchestration cancelled")
        except Exception as exc:
            logger.exception("Orchestration failed")
            await self._broadcast("error", {"message": str(exc)})
        finally:
            self._orchestrator = None

    # ---- Routes ----------------------------------------------------------

    def _register_routes(self):
        app = self.app

        @app.get("/")
        async def index():
            return HTMLResponse(self._html)

        @app.get("/events")
        async def sse_events(request: Request):
            queue: asyncio.Queue = asyncio.Queue()

            async with self._lock:
                self._queues.append(queue)

            async def event_generator():
                try:
                    while True:
                        if await request.is_disconnected():
                            break
                        try:
                            msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                        except asyncio.TimeoutError:
                            # Send keepalive comment
                            yield {"comment": "keepalive"}
                            continue

                        yield {
                            "event": msg["event"],
                            "data": json.dumps(msg["data"]),
                        }

                        # Drain extra items to keep latency low
                        while not queue.empty():
                            extra = queue.get_nowait()
                            yield {
                                "event": extra["event"],
                                "data": json.dumps(extra["data"]),
                            }
                finally:
                    async with self._lock:
                        self._queues.remove(queue)

            return EventSourceResponse(event_generator())

        @app.post("/api/run")
        async def api_run(body: RunRequest):
            if self._orchestrator is not None:
                return JSONResponse(
                    status_code=409,
                    content={"error": "Orchestration already running"},
                )
            # Fire-and-forget the orchestration in background
            asyncio.create_task(
                self._run_orchestration(body.goal, body.context)
            )
            return JSONResponse({"status": "started", "goal": body.goal})

        @app.get("/api/status")
        async def api_status():
            running = self._orchestrator is not None
            return JSONResponse({"running": running})

    # ---- Start / stop ----------------------------------------------------

    async def start(self):
        """Start the uvicorn server (blocking)."""
        config = uvicorn.Config(
            app=self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)
        logger.info("Dashboard starting on http://%s:%s", self.host, self.port)
        await self._server.serve()
