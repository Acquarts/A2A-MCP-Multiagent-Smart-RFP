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
# Maps (agent_id, tool_name) -> (async_function, PydanticInputModel, description)
# Descriptions must match the MCP server docstrings so Claude gets identical context.

_TOOL_REGISTRY: dict[tuple[str, str], tuple[Any, Any, str]] = {
    # Client Research
    ("client_research", "search_company_info"): (
        lambda p: search_company_info(
            company_name=p.company_name,
            additional_context=p.additional_context,
            response_format=p.response_format,
        ),
        SearchCompanyInput,
        "Research a company by searching the web and analyzing results with AI. "
        "Searches for company details including sector, size, funding, technologies, "
        "key people, and recent news. Returns a structured company profile.",
    ),
    ("client_research", "analyze_rfp_document"): (
        lambda p: analyze_rfp_document(
            rfp_text=p.rfp_text,
            response_format=p.response_format,
        ),
        AnalyzeRFPInput,
        "Analyze an RFP document to extract key requirements and information. "
        "Uses AI to parse and structure the RFP content, identifying business "
        "requirements, technical specs, budget indicators, timeline, evaluation "
        "criteria, and potential risks.",
    ),
    ("client_research", "search_linkedin_company"): (
        lambda p: search_linkedin_company(
            company_name=p.company_name,
            find_decision_makers=p.find_decision_makers,
            response_format=p.response_format,
        ),
        SearchLinkedInInput,
        "Search for a company's LinkedIn presence and key decision makers. "
        "Uses web search to find LinkedIn company pages and profiles of "
        "executives (CTO, CEO, VP Engineering, Directors).",
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
        "Search internal project history by keywords, sector, or requirements. "
        "Uses keyword matching plus AI-powered semantic ranking to find the "
        "most relevant past projects. Useful for finding similar work to "
        "reference in proposals.",
    ),
    ("knowledge_base", "get_project_details"): (
        lambda p: get_project_details(
            project_id=p.project_id,
            response_format=p.response_format,
        ),
        GetProjectDetailsInput,
        "Get full details of a specific project by its ID. "
        "Returns complete information including team size, duration, budget, "
        "tech stack, features, outcomes, and challenges.",
    ),
    ("knowledge_base", "search_tech_stack"): (
        lambda p: search_tech_stack(
            technologies=p.technologies,
            match_all=p.match_all,
            response_format=p.response_format,
        ),
        SearchTechStackInput,
        "Find projects that use specific technologies. "
        "Search by one or more technologies to find relevant experience. "
        "Can match projects using ANY or ALL of the specified technologies.",
    ),
    ("knowledge_base", "get_case_studies"): (
        lambda p: get_case_studies(
            client_sector=p.client_sector,
            project_type=p.project_type,
            response_format=p.response_format,
        ),
        GetCaseStudiesInput,
        "Retrieve case studies relevant to a target client's sector and project type. "
        "Finds completed projects with successful outcomes that serve as "
        "social proof in proposals.",
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
        "Generate a complete technical/commercial proposal document. "
        "Combines client research, internal knowledge base, and pricing data "
        "into a structured, professional proposal with all standard sections: "
        "Executive Summary, Project Understanding, Solution, Methodology, "
        "Team, Case Studies, Investment, and Next Steps.",
    ),
    ("proposal_writer", "generate_timeline"): (
        lambda p: generate_timeline(
            project_description=p.project_description,
            total_weeks=p.total_weeks,
            language=p.language,
            output_format=p.output_format,
        ),
        GenerateTimelineInput,
        "Generate a detailed project timeline with phases and milestones. "
        "Creates a phase-by-phase breakdown including Discovery, Design, "
        "Development, Testing, Deployment, and Post-launch support.",
    ),
    ("proposal_writer", "generate_executive_summary"): (
        lambda p: generate_executive_summary(
            full_proposal=p.full_proposal,
            max_words=p.max_words,
            language=p.language,
            output_format=p.output_format,
        ),
        GenerateExecutiveSummaryInput,
        "Generate a concise executive summary from a full proposal. "
        "Distills the proposal into a compelling summary highlighting "
        "the client's need, proposed solution, experience, and ROI.",
    ),
    ("proposal_writer", "export_proposal_docx"): (
        lambda p: export_proposal_docx(
            proposal_markdown=p.proposal_markdown,
            client_name=p.client_name,
            project_title=p.project_title,
            company_name=p.company_name,
        ),
        ExportProposalDocxInput,
        "Export a markdown proposal to a professional Word document (.docx). "
        "Creates a formatted DOCX file with cover page, styled sections, "
        "tables, headers/footers with page numbers, and company branding. "
        "The proposal must be in markdown format (output from generate_proposal).",
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
        "Generate a full project cost estimation based on scope analysis. "
        "Uses AI to analyze the project description, determine the required "
        "team composition, estimate hours per role, apply complexity multipliers, "
        "and calculate total cost with phase breakdown.",
    ),
    ("pricing", "estimate_from_roles"): (
        lambda p: estimate_from_roles(
            roles=p.roles,
            discount_tier=p.discount_tier,
            response_format=p.response_format,
        ),
        EstimateFromRolesInput,
        "Calculate project cost from a manually defined team composition. "
        "Useful when you already know the team and hours needed. "
        "Supports both predefined roles (from rate card) and custom roles.",
    ),
    ("pricing", "get_rate_card"): (
        lambda p: get_rate_card(
            response_format=p.response_format,
        ),
        GetRateCardInput,
        "Retrieve the current rate card with all roles, rates, and pricing rules. "
        "Returns hourly rates per role, complexity multipliers, discount tiers, "
        "and phase distribution percentages.",
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
        for (agent_id, tool_name), (_, model_class, description) in _TOOL_REGISTRY.items():
            if agent_id not in self._connected:
                continue
            if agent_id not in all_tools:
                all_tools[agent_id] = []

            all_tools[agent_id].append({
                "name": tool_name,
                "description": description,
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

        fn, model_class, _ = _TOOL_REGISTRY[key]
        try:
            # Unwrap "params" wrapper if present — MCP servers expect this
            # format but Pydantic models take flat arguments.
            args = arguments.get("params", arguments) if "params" in arguments else arguments
            params = model_class(**args)
            result = await fn(params)
            return result
        except Exception as e:
            logger.error(f"Error calling {agent_id}/{tool_name}: {e}")
            return json.dumps({"error": f"Tool call failed: {str(e)}"})