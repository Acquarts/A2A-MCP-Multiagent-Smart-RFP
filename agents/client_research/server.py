"""Client Research Agent — MCP Server.

Exposes tools for researching client companies:
- search_company_info: Web search + Claude analysis
- analyze_rfp_document: RFP text extraction and structuring
- search_linkedin_company: LinkedIn profile and decision maker search
"""

import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mcp.server.fastmcp import FastMCP

from agents.client_research.models import (
    SearchCompanyInput,
    AnalyzeRFPInput,
    SearchLinkedInInput,
)
from agents.client_research.tools import (
    search_company_info,
    analyze_rfp_document,
    search_linkedin_company,
)

# ── MCP Server ─────────────────────────────────────────────────────

mcp = FastMCP("client_research_mcp")


@mcp.tool(
    name="search_company_info",
    annotations={
        "title": "Search Company Information",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_search_company(params: SearchCompanyInput) -> str:
    """Research a company by searching the web and analyzing results with AI.

    Searches for company details including sector, size, funding, technologies,
    key people, and recent news. Returns a structured company profile.

    Args:
        params (SearchCompanyInput): Contains:
            - company_name (str): Name of the company to research
            - additional_context (Optional[str]): Extra context for search
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Company profile in the requested format
    """
    return await search_company_info(
        company_name=params.company_name,
        additional_context=params.additional_context,
        response_format=params.response_format,
    )


@mcp.tool(
    name="analyze_rfp_document",
    annotations={
        "title": "Analyze RFP Document",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_analyze_rfp(params: AnalyzeRFPInput) -> str:
    """Analyze an RFP document to extract key requirements and information.

    Uses AI to parse and structure the RFP content, identifying business
    requirements, technical specs, budget indicators, timeline, evaluation
    criteria, and potential risks.

    Args:
        params (AnalyzeRFPInput): Contains:
            - rfp_text (str): Full text of the RFP document
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Structured RFP analysis in the requested format
    """
    return await analyze_rfp_document(
        rfp_text=params.rfp_text,
        response_format=params.response_format,
    )


@mcp.tool(
    name="search_linkedin_company",
    annotations={
        "title": "Search LinkedIn Company Profile",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def tool_search_linkedin(params: SearchLinkedInInput) -> str:
    """Search for a company's LinkedIn presence and key decision makers.

    Uses web search to find LinkedIn company pages and profiles of
    executives (CTO, CEO, VP Engineering, Directors).

    Args:
        params (SearchLinkedInInput): Contains:
            - company_name (str): Company to search on LinkedIn
            - find_decision_makers (bool): Whether to search for executives
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: LinkedIn research results in the requested format
    """
    return await search_linkedin_company(
        company_name=params.company_name,
        find_decision_makers=params.find_decision_makers,
        response_format=params.response_format,
    )


# ── Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
