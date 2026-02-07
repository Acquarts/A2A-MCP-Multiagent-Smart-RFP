"""A2A Orchestrator — Coordinates agents to fulfill user requests.

Uses Claude as the reasoning engine to:
1. Understand the user's request
2. Discover available agents via their Agent Cards
3. Plan which agents/tools to call and in what order
4. Execute the plan by calling agent MCP tools
5. Synthesize results into a final response
"""

import json
import copy
import logging
import asyncio
from typing import Any

import httpx

from config.settings import settings
from orchestrator.agent_cards import (
    AGENT_REGISTRY,
    AgentCard,
    AgentStatus,
)
from orchestrator.mcp_client import MCPAgentPool

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_TIMEOUT = 120.0

ORCHESTRATOR_SYSTEM_PROMPT = """You are the orchestrator of a Smart RFP/Proposal Agent system.
Your job is to coordinate specialized agents to help users create commercial proposals.

## Available Agents and Tools
{agent_context}

## Your Workflow
1. Analyze the user's request
2. Decide which tool(s) to call and in what order
3. Use tool calls to delegate work to specialized agents
4. After receiving tool results, synthesize a final response for the user

## Full Proposal Workflow (when user asks for a complete proposal)
1. **Research**: Use client_research tools to investigate the company
2. **Knowledge Base**: Search for similar past projects and case studies
3. **Pricing**: Estimate project costs based on scope
4. **Generate Proposal**: Use proposal_writer__generate_proposal with all gathered data
5. **Export to DOCX**: If user requests DOCX/Word export, use proposal_writer__export_proposal_docx passing the full markdown proposal

## Rules
- Always start by researching the client company if a company name is mentioned
- If an RFP document text is provided, analyze it with the RFP tool
- Search LinkedIn for decision makers when preparing a proposal
- Combine results from multiple tools into a coherent summary
- If a required agent is offline, inform the user what's missing
- Respond in the same language the user uses
- IMPORTANT: You CAN export proposals to DOCX using the export_proposal_docx tool. Always use it when the user asks for Word/DOCX export.
- When exporting to DOCX, pass the FULL markdown content of the proposal as proposal_markdown parameter
"""


class Orchestrator:
    """A2A Orchestrator using Claude for reasoning and MCP for tool execution."""

    def __init__(self):
        self.pool = MCPAgentPool()
        self._conversation_history: list[dict[str, Any]] = []
        self._pending_proposal_md: str | None = None
        self._pending_proposal_client: str | None = None

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Connect to all available agents."""
        missing = settings.validate()
        if missing:
            raise RuntimeError(f"Missing required config: {', '.join(missing)}")

        for card in AGENT_REGISTRY.values():
            if card.status == AgentStatus.AVAILABLE:
                try:
                    await self.pool.connect_agent(card)
                    logger.info(f"✅ Agent connected: {card.name}")
                except Exception as e:
                    logger.error(f"❌ Failed to connect {card.name}: {e}")

        connected = self.pool.get_available_agents()
        logger.info(f"🚀 Orchestrator ready. Agents online: {connected}")

    async def stop(self) -> None:
        """Disconnect all agents."""
        await self.pool.disconnect_all()
        logger.info("🛑 Orchestrator stopped.")

    # ── Agent Discovery (A2A pattern) ──────────────────────────────

    def _build_agent_context(self, tools_by_agent: dict[str, list[dict]]) -> str:
        """Build context string describing available agents for Claude."""
        lines = []
        for agent_id, card in AGENT_REGISTRY.items():
            status_icon = "🟢" if card.status == AgentStatus.AVAILABLE else "🔴"
            lines.append(f"\n### {status_icon} {card.name} (id: {agent_id})")
            lines.append(f"Description: {card.description}")

            if agent_id in tools_by_agent:
                lines.append("Tools:")
                for tool in tools_by_agent[agent_id]:
                    lines.append(f"  - **{tool['name']}**: {tool.get('description', 'N/A')}")
            elif card.status == AgentStatus.OFFLINE:
                lines.append("Status: OFFLINE — not available yet")

        return "\n".join(lines)

    def _resolve_schema_refs(self, schema: dict) -> dict:
        """Resolve $defs/$ref and anyOf nullables in JSON Schema.

        Pydantic v2 generates schemas with $defs for enums and nested models,
        and uses anyOf for Optional types. Claude's tool use API doesn't
        support these, so we inline/simplify them.
        """
        defs = schema.pop("$defs", {})

        def _resolve(obj):
            if isinstance(obj, dict):
                # Resolve $ref
                if "$ref" in obj:
                    ref_path = obj["$ref"]
                    ref_name = ref_path.split("/")[-1]
                    if ref_name in defs:
                        return _resolve(defs[ref_name])
                    return obj

                # Simplify anyOf with null (Optional types)
                if "anyOf" in obj:
                    non_null = [s for s in obj["anyOf"] if s != {"type": "null"}]
                    if len(non_null) == 1:
                        resolved = _resolve(non_null[0])
                        # Preserve description and default if present
                        for key in ("description", "default", "title"):
                            if key in obj:
                                resolved[key] = obj[key]
                        return resolved

                return {k: _resolve(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_resolve(item) for item in obj]
            return obj

        return _resolve(schema)

    def _build_claude_tools(self, tools_by_agent: dict[str, list[dict]]) -> list[dict]:
        """Convert MCP tools to Claude API tool format."""
        claude_tools = []
        for agent_id, tools in tools_by_agent.items():
            for tool in tools:
                # Clean up schema: resolve $defs/$ref and anyOf
                raw_schema = tool.get("input_schema", {"type": "object", "properties": {}})
                clean_schema = self._resolve_schema_refs(copy.deepcopy(raw_schema))

                claude_tools.append({
                    "name": f"{agent_id}__{tool['name']}",
                    "description": f"[Agent: {agent_id}] {tool.get('description', '')}",
                    "input_schema": clean_schema,
                })
        return claude_tools

    # ── Execution ──────────────────────────────────────────────────

    async def _call_claude(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        max_retries: int = 5,
    ) -> dict:
        """Make a request to Claude API with tool use and retry on rate limits."""
        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=ANTHROPIC_TIMEOUT) as client:
                response = await client.post(
                    ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": settings.anthropic_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": ANTHROPIC_MODEL,
                        "max_tokens": 4096,
                        "system": system_prompt,
                        "messages": messages,
                        "tools": tools if tools else [],
                    },
                )

                if response.status_code == 429:
                    wait_time = (attempt + 1) * 15  # 15s, 30s, 45s, 60s, 75s
                    logger.warning(f"⏳ Rate limited. Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    continue

                if response.status_code >= 400:
                    logger.error(f"❌ Claude API error {response.status_code}: {response.text}")

                response.raise_for_status()
                return response.json()

        # Last attempt failed
        raise RuntimeError("Claude API rate limit exceeded after all retries. Wait a minute and try again.")

    async def _execute_tool_call(self, tool_name: str, tool_input: dict) -> str:
        """Route a Claude tool call to the correct agent MCP server.

        Tool names arrive as 'agent_id__tool_name', so we split to route.
        """
        parts = tool_name.split("__", 1)
        if len(parts) != 2:
            return json.dumps({"error": f"Invalid tool name format: {tool_name}"})

        agent_id, mcp_tool_name = parts
        logger.info(f"🔧 Calling tool '{mcp_tool_name}' on agent '{agent_id}'")

        result = await self.pool.call_agent_tool(agent_id, mcp_tool_name, tool_input)
        return result

    # ── Main Chat Loop ─────────────────────────────────────────────

    async def chat(self, user_message: str) -> str:
        """Process a user message through the full A2A orchestration loop.

        1. Discover available tools from connected agents
        2. Send user message + tools to Claude
        3. If Claude wants to use tools → execute them → send results back
        4. Repeat until Claude produces a final text response
        """
        # Step 1: Discover tools from connected agents
        tools_by_agent = await self.pool.get_all_tools()
        agent_context = self._build_agent_context(tools_by_agent)
        claude_tools = self._build_claude_tools(tools_by_agent)
        system_prompt = ORCHESTRATOR_SYSTEM_PROMPT.format(agent_context=agent_context)

        # Step 2: Add user message to conversation
        self._conversation_history.append({"role": "user", "content": user_message})

        # Step 3: Agentic loop — keep calling Claude until it stops using tools
        max_iterations = 10

        logger.info(f"📋 Sending {len(claude_tools)} tools to Claude")
        for t in claude_tools:
            logger.info(f"   Tool: {t['name']}")
        for iteration in range(max_iterations):
            logger.info(f"🔄 Orchestrator iteration {iteration + 1}")

            response = await self._call_claude(
                system_prompt=system_prompt,
                messages=self._conversation_history,
                tools=claude_tools,
            )

            stop_reason = response.get("stop_reason")
            content_blocks = response.get("content", [])

            # Add assistant response to history
            self._conversation_history.append({"role": "assistant", "content": content_blocks})

            # If Claude is done (no more tool calls), extract final text
            if stop_reason == "end_turn" or stop_reason != "tool_use":
                final_text = ""
                for block in content_blocks:
                    if block.get("type") == "text":
                        final_text += block["text"]

                # Auto-export: if proposal was generated and user wanted DOCX
                wants_docx = any(kw in user_message.lower() for kw in ["docx", "word", "exporta", "documento"])
                if self._pending_proposal_md and self._pending_proposal_client and wants_docx:
                    logger.info(f"📄 Auto-exporting proposal to DOCX for {self._pending_proposal_client}...")
                    try:
                        export_result = await self._execute_tool_call(
                            "proposal_writer__export_proposal_docx",
                            {"params": {
                                "proposal_markdown": self._pending_proposal_md,
                                "client_name": self._pending_proposal_client,
                                "project_title": f"Technical Proposal — {self._pending_proposal_client}",
                            }},
                        )
                        logger.info(f"📄 DOCX export result: {export_result[:300]}...")
                        final_text += f"\n\n---\n📄 **Documento DOCX generado automáticamente.**\n{export_result}"
                        # Clear after successful export
                        self._pending_proposal_md = None
                        self._pending_proposal_client = None
                    except Exception as e:
                        logger.error(f"❌ Auto-export failed: {e}")
                        final_text += f"\n\n⚠️ No se pudo exportar a DOCX automáticamente: {e}"

                return final_text

            # Step 4: Execute tool calls and collect results
            tool_results = []

            for block in content_blocks:
                if block.get("type") == "tool_use":
                    tool_id = block["id"]
                    tool_name = block["name"]
                    tool_input = block["input"]

                    logger.info(f"📨 Tool call: {tool_name} with input: {json.dumps(tool_input)[:200]}")
                    result = await self._execute_tool_call(tool_name, tool_input)
                    logger.info(f"📬 Tool result preview: {result[:200]}...")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result,
                    })

                    # Track proposal generation for auto-export
                    if tool_name == "proposal_writer__generate_proposal" and "📄 Technical Proposal" in result:
                        self._pending_proposal_md = result
                        params = tool_input.get("params", tool_input)
                        self._pending_proposal_client = params.get("client_name", "Client")

            # Add tool results to conversation for next iteration
            self._conversation_history.append({"role": "user", "content": tool_results})

        return "⚠️ Maximum orchestration iterations reached. Partial results may be available."

    def reset_conversation(self) -> None:
        """Clear conversation history for a new session."""
        self._conversation_history.clear()
        self._pending_proposal_md = None
        self._pending_proposal_client = None