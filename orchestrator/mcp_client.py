"""MCP Client — Connects the orchestrator to agent MCP servers.

Manages the lifecycle of MCP server connections and provides
a clean interface for calling tools on remote agents.
"""

import json
import logging
import sys
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from orchestrator.agent_cards import AgentCard, AgentStatus

logger = logging.getLogger(__name__)


class MCPAgentConnection:
    """Manages a connection to a single agent's MCP server."""

    def __init__(self, card: AgentCard):
        self.card = card
        self._session: ClientSession | None = None
        self._client_ctx = None
        self._session_ctx = None

    @property
    def is_connected(self) -> bool:
        return self._session is not None

    async def connect(self) -> None:
        """Start the MCP server subprocess and establish connection."""
        if self.card.status == AgentStatus.OFFLINE:
            logger.warning(f"Agent '{self.card.agent_id}' is offline, skipping connection.")
            return

        # Use sys.executable to ensure subprocesses run with the same
        # Python interpreter (and installed packages) as the main process.
        # This is critical on Streamlit Cloud where "python" may not
        # point to the venv with dependencies installed.
        command = self.card.mcp_server_command[0]
        if command == "python":
            command = sys.executable

        server_params = StdioServerParameters(
            command=command,
            args=self.card.mcp_server_command[1:],
        )

        self._client_ctx = stdio_client(server_params)
        read_stream, write_stream = await self._client_ctx.__aenter__()

        self._session_ctx = ClientSession(read_stream, write_stream)
        self._session = await self._session_ctx.__aenter__()

        await self._session.initialize()
        logger.info(f"✅ Connected to agent '{self.card.name}'")

    async def disconnect(self) -> None:
        """Close the MCP session and stop the server."""
        if self._session_ctx:
            await self._session_ctx.__aexit__(None, None, None)
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
        self._session = None
        logger.info(f"🔌 Disconnected from agent '{self.card.name}'")

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all tools available on this agent's MCP server."""
        if not self._session:
            return []
        result = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.inputSchema,
            }
            for tool in result.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Call a specific tool on the agent's MCP server."""
        if not self._session:
            return json.dumps({"error": f"Agent '{self.card.agent_id}' is not connected"})

        try:
            result = await self._session.call_tool(tool_name, arguments)

            # Extract text from MCP response content blocks
            texts = []
            for block in result.content:
                if hasattr(block, "text"):
                    texts.append(block.text)
            return "\n".join(texts) if texts else json.dumps({"result": "empty response"})

        except Exception as e:
            logger.error(f"Error calling {tool_name} on {self.card.agent_id}: {e}")
            return json.dumps({"error": f"Tool call failed: {str(e)}"})


class MCPAgentPool:
    """Manages connections to all registered agent MCP servers."""

    def __init__(self):
        self._connections: dict[str, MCPAgentConnection] = {}

    async def connect_agent(self, card: AgentCard) -> None:
        """Connect to a single agent."""
        conn = MCPAgentConnection(card)
        await conn.connect()
        if conn.is_connected:
            self._connections[card.agent_id] = conn

    async def disconnect_all(self) -> None:
        """Disconnect from all agents."""
        for conn in self._connections.values():
            await conn.disconnect()
        self._connections.clear()

    def get_connection(self, agent_id: str) -> MCPAgentConnection | None:
        """Get a connection by agent ID."""
        return self._connections.get(agent_id)

    def get_available_agents(self) -> list[str]:
        """List IDs of all connected agents."""
        return list(self._connections.keys())

    async def get_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """Get all tools from all connected agents, grouped by agent_id."""
        all_tools = {}
        for agent_id, conn in self._connections.items():
            all_tools[agent_id] = await conn.list_tools()
        return all_tools

    async def call_agent_tool(
        self, agent_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """Call a tool on a specific agent."""
        conn = self._connections.get(agent_id)
        if not conn:
            return json.dumps({"error": f"Agent '{agent_id}' not found or not connected"})
        return await conn.call_tool(tool_name, arguments)
