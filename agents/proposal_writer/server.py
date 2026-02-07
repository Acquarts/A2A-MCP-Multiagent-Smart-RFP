"""Proposal Writer Agent — MCP Server.

Exposes tools for generating professional proposals:
- generate_proposal: Full technical/commercial proposal
- generate_timeline: Project timeline with phases and deliverables
- generate_executive_summary: Concise summary from a full proposal
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mcp.server.fastmcp import FastMCP

from agents.proposal_writer.models import (
    GenerateProposalInput,
    GenerateTimelineInput,
    GenerateExecutiveSummaryInput,
    ExportProposalDocxInput,
)
from agents.proposal_writer.tools import (
    generate_proposal,
    generate_timeline,
    generate_executive_summary,
    export_proposal_docx,
)

# ── MCP Server ─────────────────────────────────────────────────────

mcp = FastMCP("proposal_writer_mcp")


@mcp.tool(
    name="generate_proposal",
    annotations={
        "title": "Generate Full Proposal",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def tool_generate_proposal(params: GenerateProposalInput) -> str:
    """Generate a complete technical/commercial proposal document.

    Combines client research, internal knowledge base, and pricing data
    into a structured, professional proposal with all standard sections:
    Executive Summary, Project Understanding, Solution, Methodology,
    Team, Case Studies, Investment, and Next Steps.

    Args:
        params (GenerateProposalInput): Contains:
            - client_name (str): Name of the client company
            - project_description (str): What the client needs
            - client_research (Optional[str]): Research results about the client
            - relevant_projects (Optional[str]): Similar past projects
            - pricing_info (Optional[str]): Budget estimation
            - language (ProposalLanguage): 'en' or 'es'
            - output_format (OutputFormat): 'markdown' or 'json'

    Returns:
        str: Complete proposal document
    """
    return await generate_proposal(
        client_name=params.client_name,
        project_description=params.project_description,
        client_research=params.client_research,
        relevant_projects=params.relevant_projects,
        pricing_info=params.pricing_info,
        language=params.language,
        output_format=params.output_format,
    )


@mcp.tool(
    name="generate_timeline",
    annotations={
        "title": "Generate Project Timeline",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def tool_generate_timeline(params: GenerateTimelineInput) -> str:
    """Generate a detailed project timeline with phases and milestones.

    Creates a phase-by-phase breakdown including Discovery, Design,
    Development, Testing, Deployment, and Post-launch support.

    Args:
        params (GenerateTimelineInput): Contains:
            - project_description (str): Project scope description
            - total_weeks (Optional[int]): Target duration in weeks
            - language (ProposalLanguage): 'en' or 'es'
            - output_format (OutputFormat): 'markdown' or 'json'

    Returns:
        str: Timeline with phases, durations, and deliverables
    """
    return await generate_timeline(
        project_description=params.project_description,
        total_weeks=params.total_weeks,
        language=params.language,
        output_format=params.output_format,
    )


@mcp.tool(
    name="generate_executive_summary",
    annotations={
        "title": "Generate Executive Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def tool_generate_summary(params: GenerateExecutiveSummaryInput) -> str:
    """Generate a concise executive summary from a full proposal.

    Distills the proposal into a compelling summary highlighting
    the client's need, proposed solution, experience, and ROI.

    Args:
        params (GenerateExecutiveSummaryInput): Contains:
            - full_proposal (str): Complete proposal text to summarize
            - max_words (int): Maximum word count (50-1000)
            - language (ProposalLanguage): 'en' or 'es'
            - output_format (OutputFormat): 'markdown' or 'json'

    Returns:
        str: Executive summary
    """
    return await generate_executive_summary(
        full_proposal=params.full_proposal,
        max_words=params.max_words,
        language=params.language,
        output_format=params.output_format,
    )


@mcp.tool(
    name="export_proposal_docx",
    annotations={
        "title": "Export Proposal to DOCX",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_export_docx(params: ExportProposalDocxInput) -> str:
    """Export a markdown proposal to a professional Word document (.docx).

    Creates a formatted DOCX file with cover page, styled sections,
    tables, headers/footers with page numbers, and company branding.
    The proposal must be in markdown format (output from generate_proposal).

    Args:
        params (ExportProposalDocxInput): Contains:
            - proposal_markdown (str): Full proposal in markdown
            - client_name (str): Client company name for cover page
            - project_title (str): Title for the cover page
            - company_name (str): Your company name for branding

    Returns:
        str: JSON with file path and status
    """
    return await export_proposal_docx(
        proposal_markdown=params.proposal_markdown,
        client_name=params.client_name,
        project_title=params.project_title,
        company_name=params.company_name,
    )


# ── Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()