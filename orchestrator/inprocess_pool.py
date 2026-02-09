"""In-Process Agent Pool — Calls agent tools directly without subprocesses.

Provides the same interface as MCPAgentPool but imports and calls tool
functions in-process. This avoids spawning 4 Python subprocesses, which
is critical for memory-constrained environments like Streamlit Cloud.
"""

import json
import logging
from typing import Any

from orchestrator.agent_cards import AGENT_REGISTRY, AgentStatus

logger = logging.getLogger(__name__)

# ── Tool function imports ────────────────────────────────────────────

from agents.client_research.tools import (
    search_company_info,
    analyze_rfp_document,
    search_linkedin_company,
)
from agents.client_research.models import (
    SearchCompanyInput,
    AnalyzeRFPInput,
    SearchLinkedInInput,
)

from agents.knowledge_base.tools import (
    search_past_projects,
    get_project_details,
    search_tech_stack,
    get_case_studies,
)
from agents.knowledge_base.models import (
    SearchProjectsInput,
    GetProjectDetailsInput,
    SearchTechStackInput,
    GetCaseStudiesInput,
)

from agents.proposal_writer.tools import (
    generate_proposal,
    generate_timeline,
    generate_executive_summary,
    export_proposal_docx,
)
from agents.proposal_writer.models import (
    GenerateProposalInput,
    GenerateTimelineInput,
    GenerateExecutiveSummaryInput,
    ExportProposalDocxInput,
)

from agents.pricing.tools import (
    estimate_project,
    estimate_from_roles,
    get_rate_card,
)
from agents.pricing.models import (
    EstimateProjectInput,
    EstimateFromRolesInput,
    GetRateCardInput,
)


# ── Tool Registry ────────────────────────────────────────────────────
# Maps (agent_id, tool_name) -> (async_function, PydanticInputModel)

_TOOL_REGISTRY: dict[tuple[str, str], tuple[Any, Any]] = {
    # Client Research
    ("client_research", "search_company_info"): (
        lambda p: search_company_info(
            company_name=p.company_name,
            additional_context=p.additional_context,
            response_format=p.response_format,
        ),
        SearchCompanyInput,
    ),
    ("client_research", "analyze_rfp_document"): (
        lambda p: analyze_rfp_document(
            rfp_text=p.rfp_text,
            response_format=p.response_format,
        ),
        AnalyzeRFPInput,
    ),
    ("client_research", "search_linkedin_company"): (
        lambda p: search_linkedin_company(
            company_name=p.company_name,
            find_decision_makers=p.find_decision_makers,
            response_format=p.response_format,
        ),
        SearchLinkedInInput,
    ),
    # Knowledge Base
    ("knowledge_base", "search_past_projects"): (
        lambda p: search_past_projects(
            query=p.query,
            sector=p.sector,
            max_results=p.max_results,
            response_format=p.response_format,
        ),
        SearchProjectsInput,
    ),
    ("knowledge_base", "get_project_details"): (
        lambda p: get_project_details(
            project_id=p.project_id,
            response_format=p.response_format,
        ),
        GetProjectDetailsInput,
    ),
    ("knowledge_base", "search_tech_stack"): (
        lambda p: search_tech_stack(
            technologies=p.technologies,
            match_all=p.match_all,
            response_format=p.response_format,
        ),
        SearchTechStackInput,
    ),
    ("knowledge_base", "get_case_studies"): (
        lambda p: get_case_studies(
            client_sector=p.client_sector,
            project_type=p.project_type,
            response_format=p.response_format,
        ),
        GetCaseStudiesInput,
    ),
    # Proposal Writer
    ("proposal_writer", "generate_proposal"): (
        lambda p: generate_proposal(
            client_name=p.client_name,
            project_description=p.project_description,
            client_research=p.client_research,
            relevant_projects=p.relevant_projects,
            pricing_info=p.pricing_info,
            language=p.language,
            output_format=p.output_format,
        ),
        GenerateProposalInput,
    ),
    ("proposal_writer", "generate_timeline"): (
        lambda p: generate_timeline(
            project_description=p.project_description,
            total_weeks=p.total_weeks,
            language=p.language,
            output_format=p.output_format,
        ),
        GenerateTimelineInput,
    ),
    ("proposal_writer", "generate_executive_summary"): (
        lambda p: generate_executive_summary(
            full_proposal=p.full_proposal,
            max_words=p.max_words,
            language=p.language,
            output_format=p.output_format,
        ),
        GenerateExecutiveSummaryInput,
    ),
    ("proposal_writer", "export_proposal_docx"): (
        lambda p: export_proposal_docx(
            proposal_markdown=p.proposal_markdown,
            client_name=p.client_name,
            project_title=p.project_title,
            company_name=p.company_name,
        ),
        ExportProposalDocxInput,
    ),
    # Pricing
    ("pricing", "estimate_project"): (
        lambda p: estimate_project(
            project_description=p.project_description,
            duration_weeks=p.duration_weeks,
            complexity=p.complexity,
            discount_tier=p.discount_tier,
            response_format=p.response_format,
        ),
        EstimateProjectInput,
    ),
    ("pricing", "estimate_from_roles"): (
        lambda p: estimate_from_roles(
            roles=p.roles,
            discount_tier=p.discount_tier,
            response_format=p.response_format,
        ),
        EstimateFromRolesInput,
    ),
    ("pricing", "get_rate_card"): (
        lambda p: get_rate_card(
            response_format=p.response_format,
        ),
        GetRateCardInput,
    ),
}


def _build_tool_schema(model_class) -> dict:
    """Generate a JSON Schema from a Pydantic model for Claude's tool API."""
    schema = model_class.model_json_schema()
    # Remove $defs — Claude doesn't support them
    schema.pop("$defs", None)
    return schema


# ── InProcessAgentPool ───────────────────────────────────────────────

class InProcessAgentPool:
    """Drop-in replacement for MCPAgentPool that calls tools directly.

    Same public interface: connect_agent, disconnect_all, get_available_agents,
    get_all_tools, call_agent_tool.
    """

    def __init__(self):
        self._connected: list[str] = []

    async def connect_agent(self, card) -> None:
        """Mark an agent as connected (no subprocess needed)."""
        if card.status == AgentStatus.AVAILABLE:
            self._connected.append(card.agent_id)
            logger.info(f"✅ Agent registered (in-process): {card.name}")

    async def disconnect_all(self) -> None:
        """Nothing to disconnect in-process."""
        self._connected.clear()

    def get_available_agents(self) -> list[str]:
        return list(self._connected)

    async def get_all_tools(self) -> dict[str, list[dict[str, Any]]]:
        """Return tool definitions grouped by agent, with JSON schemas."""
        all_tools: dict[str, list[dict]] = {}
        for (agent_id, tool_name), (_, model_class) in _TOOL_REGISTRY.items():
            if agent_id not in self._connected:
                continue
            if agent_id not in all_tools:
                all_tools[agent_id] = []

            # Get description from the tool function's docstring or model
            desc = model_class.__doc__ or tool_name

            all_tools[agent_id].append({
                "name": tool_name,
                "description": desc,
                "input_schema": _build_tool_schema(model_class),
            })
        return all_tools

    async def call_agent_tool(
        self, agent_id: str, tool_name: str, arguments: dict[str, Any]
    ) -> str:
        """Call a tool function directly in-process."""
        key = (agent_id, tool_name)
        if key not in _TOOL_REGISTRY:
            return json.dumps({"error": f"Tool '{tool_name}' not found on agent '{agent_id}'"})

        fn, model_class = _TOOL_REGISTRY[key]
        try:
            params = model_class(**arguments)
            result = await fn(params)
            return result
        except Exception as e:
            logger.error(f"Error calling {agent_id}/{tool_name}: {e}")
            return json.dumps({"error": f"Tool call failed: {str(e)}"})