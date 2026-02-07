"""Bridge between Streamlit's sync world and the async Orchestrator.

Creates a dedicated daemon thread running a persistent asyncio event loop.
The Orchestrator and its MCP subprocess connections live entirely on that
loop, surviving Streamlit's page reruns.
"""

import asyncio
import threading
from typing import Optional

from orchestrator.orchestrator import Orchestrator


class OrchestratorBridge:
    """Wraps the async Orchestrator for synchronous Streamlit calls."""

    def __init__(self):
        self._orchestrator = Orchestrator()
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="orchestrator-loop"
        )
        self._thread.start()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_async(self, coro, timeout: float = 180.0):
        """Submit a coroutine to the background loop and block until done."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def start(self) -> list[str]:
        """Start orchestrator and connect agents. Returns connected agent IDs."""
        self._run_async(self._orchestrator.start(), timeout=60.0)
        return self._orchestrator.pool.get_available_agents()

    def chat(self, message: str) -> str:
        """Send a message and block until response is ready (up to 5 min)."""
        return self._run_async(self._orchestrator.chat(message), timeout=300.0)

    def reset_conversation(self):
        """Clear conversation history for a new session."""
        self._orchestrator.reset_conversation()

    def stop(self):
        """Disconnect agents and stop the background loop."""
        try:
            self._run_async(self._orchestrator.stop(), timeout=30.0)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)

    @property
    def pending_proposal_md(self) -> Optional[str]:
        return self._orchestrator._pending_proposal_md

    @property
    def pending_proposal_client(self) -> Optional[str]:
        return self._orchestrator._pending_proposal_client

    @property
    def connected_agents(self) -> list[str]:
        return self._orchestrator.pool.get_available_agents()
