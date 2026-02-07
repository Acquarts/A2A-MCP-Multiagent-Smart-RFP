"""Knowledge Base Agent — MCP Server.

Exposes tools for searching internal projects and documentation:
- search_past_projects: Semantic search across project history
- get_project_details: Full details of a specific project
- search_tech_stack: Find projects by technologies used
- get_case_studies: Retrieve relevant case studies for proposals
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mcp.server.fastmcp import FastMCP

from agents.knowledge_base.models import (
    SearchProjectsInput,
    GetProjectDetailsInput,
    SearchTechStackInput,
    GetCaseStudiesInput,
)
from agents.knowledge_base.tools import (
    search_past_projects,
    get_project_details,
    search_tech_stack,
    get_case_studies,
)

# ── MCP Server ─────────────────────────────────────────────────────

mcp = FastMCP("knowledge_base_mcp")


@mcp.tool(
    name="search_past_projects",
    annotations={
        "title": "Search Past Projects",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_search_projects(params: SearchProjectsInput) -> str:
    """Search internal project history by keywords, sector, or requirements.

    Uses keyword matching plus AI-powered semantic ranking to find the
    most relevant past projects. Useful for finding similar work to
    reference in proposals.

    Args:
        params (SearchProjectsInput): Contains:
            - query (str): Natural language search (e.g., 'mobile delivery app with AI')
            - sector (Optional[str]): Filter by sector
            - max_results (int): Max projects to return (1-10)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: List of matching projects with relevance scores
    """
    return await search_past_projects(
        query=params.query,
        sector=params.sector,
        max_results=params.max_results,
        response_format=params.response_format,
    )


@mcp.tool(
    name="get_project_details",
    annotations={
        "title": "Get Project Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_get_project(params: GetProjectDetailsInput) -> str:
    """Get full details of a specific project by its ID.

    Returns complete information including team size, duration, budget,
    tech stack, features, outcomes, and challenges.

    Args:
        params (GetProjectDetailsInput): Contains:
            - project_id (str): Project ID (e.g., 'PRJ-001')
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Full project details
    """
    return await get_project_details(
        project_id=params.project_id,
        response_format=params.response_format,
    )


@mcp.tool(
    name="search_tech_stack",
    annotations={
        "title": "Search by Tech Stack",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_search_tech(params: SearchTechStackInput) -> str:
    """Find projects that use specific technologies.

    Search by one or more technologies to find relevant experience.
    Can match projects using ANY or ALL of the specified technologies.

    Args:
        params (SearchTechStackInput): Contains:
            - technologies (list[str]): Technologies to search (e.g., ['React', 'Python'])
            - match_all (bool): Require all technologies (True) or any match (False)
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Projects matching the technology criteria
    """
    return await search_tech_stack(
        technologies=params.technologies,
        match_all=params.match_all,
        response_format=params.response_format,
    )


@mcp.tool(
    name="get_case_studies",
    annotations={
        "title": "Get Relevant Case Studies",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_case_studies(params: GetCaseStudiesInput) -> str:
    """Retrieve case studies relevant to a target client's sector and project type.

    Finds completed projects with successful outcomes that serve as
    social proof in proposals.

    Args:
        params (GetCaseStudiesInput): Contains:
            - client_sector (str): Target client's sector (e.g., 'Food & Delivery')
            - project_type (Optional[str]): Type of project (e.g., 'mobile app')
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Relevant case studies with outcomes
    """
    return await get_case_studies(
        client_sector=params.client_sector,
        project_type=params.project_type,
        response_format=params.response_format,
    )


# ── Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
