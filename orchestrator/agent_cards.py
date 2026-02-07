"""A2A Agent Cards — Define capabilities of each agent in the network.

Each agent publishes an Agent Card following the A2A protocol pattern,
declaring what it can do so the orchestrator can discover and route tasks.
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class AgentSkill(BaseModel):
    """A specific capability of an agent."""
    name: str = Field(..., description="Skill identifier")
    description: str = Field(..., description="What this skill does")
    mcp_tool_name: str = Field(..., description="Corresponding MCP tool name")
    example_queries: list[str] = Field(
        default_factory=list,
        description="Example user queries that trigger this skill",
    )


class AgentStatus(str, Enum):
    """Agent availability status."""
    AVAILABLE = "available"
    BUSY = "busy"
    OFFLINE = "offline"


class AgentCard(BaseModel):
    """A2A Agent Card — declares an agent's identity and capabilities.

    This follows the A2A protocol pattern where each agent publishes
    a card so other agents (or an orchestrator) can discover it.
    """
    agent_id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Human-readable agent name")
    description: str = Field(..., description="What this agent does")
    version: str = Field(default="1.0.0")
    status: AgentStatus = Field(default=AgentStatus.AVAILABLE)
    skills: list[AgentSkill] = Field(default_factory=list)
    mcp_server_command: list[str] = Field(
        ...,
        description="Command to start the MCP server (e.g., ['python', 'agents/client_research/server.py'])",
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Other agent IDs this agent depends on",
    )

    @property
    def skill_names(self) -> list[str]:
        return [s.name for s in self.skills]

    @property
    def tool_names(self) -> list[str]:
        return [s.mcp_tool_name for s in self.skills]


# ── Agent Registry ─────────────────────────────────────────────────

CLIENT_RESEARCH_CARD = AgentCard(
    agent_id="client_research",
    name="🔍 Client Research Agent",
    description=(
        "Investigates client companies using web search and LinkedIn. "
        "Can analyze RFP documents to extract requirements, technical specs, "
        "budget indicators, and identify key decision makers."
    ),
    version="1.0.0",
    skills=[
        AgentSkill(
            name="company_research",
            description="Search and analyze company information from the web",
            mcp_tool_name="search_company_info",
            example_queries=[
                "Research Acme Corp",
                "What does this company do?",
                "Find info about the client",
            ],
        ),
        AgentSkill(
            name="rfp_analysis",
            description="Analyze an RFP document to extract structured requirements",
            mcp_tool_name="analyze_rfp_document",
            example_queries=[
                "Analyze this RFP",
                "Extract requirements from this document",
                "What does the client need?",
            ],
        ),
        AgentSkill(
            name="linkedin_research",
            description="Search LinkedIn for company profile and decision makers",
            mcp_tool_name="search_linkedin_company",
            example_queries=[
                "Find them on LinkedIn",
                "Who are the decision makers?",
                "Search LinkedIn for the company",
            ],
        ),
    ],
    mcp_server_command=["python", "agents/client_research/server.py"],
)

# Placeholder cards for future agents
KNOWLEDGE_BASE_CARD = AgentCard(
    agent_id="knowledge_base",
    name="📂 Knowledge Base Agent",
    description=(
        "Searches internal projects, case studies, and documentation "
        "to find relevant past work and reusable content for proposals."
    ),
    skills=[
        AgentSkill(
            name="project_search",
            description="Search past projects by keywords, sector, or requirements",
            mcp_tool_name="search_past_projects",
            example_queries=[
                "Find similar projects",
                "Do we have experience with mobile apps?",
                "Projects in fintech",
            ],
        ),
        AgentSkill(
            name="project_details",
            description="Get full details of a specific project by ID",
            mcp_tool_name="get_project_details",
            example_queries=[
                "Show me project PRJ-001",
                "Details of the FoodRush project",
            ],
        ),
        AgentSkill(
            name="tech_stack_search",
            description="Find projects by technologies used",
            mcp_tool_name="search_tech_stack",
            example_queries=[
                "Projects using React and Python",
                "Do we have experience with AWS?",
            ],
        ),
        AgentSkill(
            name="case_studies",
            description="Retrieve case studies relevant to a client's sector",
            mcp_tool_name="get_case_studies",
            example_queries=[
                "Case studies for a healthcare client",
                "Show success stories in delivery apps",
            ],
        ),
    ],
    mcp_server_command=["python", "agents/knowledge_base/server.py"],
)

PROPOSAL_WRITER_CARD = AgentCard(
    agent_id="proposal_writer",
    name="📝 Proposal Writer Agent",
    description=(
        "Generates professional technical and commercial proposals by combining "
        "client research, internal knowledge, and pricing into a structured document. "
        "Supports English and Spanish. Can also generate timelines and executive summaries."
    ),
    skills=[
        AgentSkill(
            name="full_proposal",
            description="Generate a complete technical/commercial proposal document",
            mcp_tool_name="generate_proposal",
            example_queries=[
                "Write the proposal for Acme Corp",
                "Generate a proposal in Spanish",
                "Create the full proposal document",
            ],
        ),
        AgentSkill(
            name="timeline",
            description="Generate a project timeline with phases and deliverables",
            mcp_tool_name="generate_timeline",
            example_queries=[
                "Create a timeline for this project",
                "How long will this take?",
                "Break down the project into phases",
            ],
        ),
        AgentSkill(
            name="executive_summary",
            description="Generate a concise executive summary from a full proposal",
            mcp_tool_name="generate_executive_summary",
            example_queries=[
                "Summarize this proposal",
                "Write an executive summary",
                "Give me the TL;DR of the proposal",
            ],
        ),
        AgentSkill(
            name="export_docx",
            description="Export a markdown proposal to a professional Word document (.docx)",
            mcp_tool_name="export_proposal_docx",
            example_queries=[
                "Export the proposal to Word",
                "Generate the DOCX file",
                "Save the proposal as a Word document",
            ],
        ),
    ],
    mcp_server_command=["python", "agents/proposal_writer/server.py"],
    dependencies=["client_research", "knowledge_base"],
)

PRICING_CARD = AgentCard(
    agent_id="pricing",
    name="💰 Pricing Agent",
    description=(
        "Estimates project costs based on scope analysis, team composition, "
        "complexity multipliers, and configurable rate cards. Uses AI to "
        "recommend team and hours, then calculates detailed cost breakdowns."
    ),
    skills=[
        AgentSkill(
            name="project_estimation",
            description="AI-powered full project cost estimation from a description",
            mcp_tool_name="estimate_project",
            example_queries=[
                "How much will this project cost?",
                "Estimate the budget",
                "What's the pricing for this scope?",
            ],
        ),
        AgentSkill(
            name="custom_estimation",
            description="Calculate cost from a manually defined team and hours",
            mcp_tool_name="estimate_from_roles",
            example_queries=[
                "Price this with 2 backend devs for 300 hours",
                "Custom team estimate",
            ],
        ),
        AgentSkill(
            name="rate_card",
            description="View current hourly rates, multipliers, and discounts",
            mcp_tool_name="get_rate_card",
            example_queries=[
                "What are our rates?",
                "Show me the rate card",
                "How much does a backend developer cost?",
            ],
        ),
    ],
    mcp_server_command=["python", "agents/pricing/server.py"],
)


# All registered agent cards
AGENT_REGISTRY: dict[str, AgentCard] = {
    "client_research": CLIENT_RESEARCH_CARD,
    "knowledge_base": KNOWLEDGE_BASE_CARD,
    "proposal_writer": PROPOSAL_WRITER_CARD,
    "pricing": PRICING_CARD,
}