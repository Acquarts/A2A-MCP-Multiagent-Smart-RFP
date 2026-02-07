"""Pricing Agent — MCP Server.

Exposes tools for project cost estimation:
- estimate_project: AI-powered full project estimation
- estimate_from_roles: Manual team composition pricing
- get_rate_card: Current rates, multipliers, and discounts
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from mcp.server.fastmcp import FastMCP

from agents.pricing.models import (
    EstimateProjectInput,
    EstimateFromRolesInput,
    GetRateCardInput,
)
from agents.pricing.tools import (
    estimate_project,
    estimate_from_roles,
    get_rate_card,
)

# ── MCP Server ─────────────────────────────────────────────────────

mcp = FastMCP("pricing_mcp")


@mcp.tool(
    name="estimate_project",
    annotations={
        "title": "Estimate Project Cost",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def tool_estimate_project(params: EstimateProjectInput) -> str:
    """Generate a full project cost estimation based on scope analysis.

    Uses AI to analyze the project description, determine the required
    team composition, estimate hours per role, apply complexity multipliers,
    and calculate total cost with phase breakdown.

    Args:
        params (EstimateProjectInput): Contains:
            - project_description (str): What needs to be built
            - duration_weeks (Optional[int]): Target duration
            - complexity (Complexity): 'low', 'medium', 'high', 'very_high'
            - discount_tier (DiscountTier): 'standard', 'long_term', 'strategic'
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Detailed cost estimation with team, phases, and totals
    """
    return await estimate_project(
        project_description=params.project_description,
        duration_weeks=params.duration_weeks,
        complexity=params.complexity,
        discount_tier=params.discount_tier,
        response_format=params.response_format,
    )


@mcp.tool(
    name="estimate_from_roles",
    annotations={
        "title": "Estimate from Custom Roles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_estimate_from_roles(params: EstimateFromRolesInput) -> str:
    """Calculate project cost from a manually defined team composition.

    Useful when you already know the team and hours needed.
    Supports both predefined roles (from rate card) and custom roles.

    Args:
        params (EstimateFromRolesInput): Contains:
            - roles (list[dict]): Team with hours per role
            - discount_tier (DiscountTier): 'standard', 'long_term', 'strategic'
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Cost breakdown by role with totals
    """
    return await estimate_from_roles(
        roles=params.roles,
        discount_tier=params.discount_tier,
        response_format=params.response_format,
    )


@mcp.tool(
    name="get_rate_card",
    annotations={
        "title": "Get Current Rate Card",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def tool_get_rate_card(params: GetRateCardInput) -> str:
    """Retrieve the current rate card with all roles, rates, and pricing rules.

    Returns hourly rates per role, complexity multipliers, discount tiers,
    and phase distribution percentages.

    Args:
        params (GetRateCardInput): Contains:
            - response_format (ResponseFormat): 'markdown' or 'json'

    Returns:
        str: Complete rate card information
    """
    return await get_rate_card(
        response_format=params.response_format,
    )


# ── Entrypoint ─────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
