"""Tool implementations for the Pricing Agent.

Uses a rate card + Claude analysis to estimate project costs
based on scope, team composition, and complexity.
"""

import json
import math
from pathlib import Path
from typing import Any

import httpx

from config.settings import settings
from shared.utils import format_json_response, handle_api_error
from agents.pricing.models import (
    ResponseFormat,
    Complexity,
    DiscountTier,
    RoleEstimate,
    PhaseEstimate,
    ProjectEstimate,
)

# ── Constants ──────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
RATE_CARD_FILE = DATA_DIR / "rate_card.json"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_TIMEOUT = 60.0

HOURS_PER_WEEK_PER_PERSON = 40


# ── Data Layer ─────────────────────────────────────────────────────

def _load_rate_card() -> dict[str, Any]:
    """Load the rate card configuration."""
    with open(RATE_CARD_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_role(rate_card: dict, role_id: str) -> dict | None:
    """Find a role in the rate card by ID."""
    return next((r for r in rate_card["roles"] if r["role_id"] == role_id), None)


def _get_discount(rate_card: dict, tier: DiscountTier) -> int:
    """Get discount percentage for a tier."""
    return rate_card.get("discount_tiers", {}).get(tier.value, 0)


# ── Claude Analysis ────────────────────────────────────────────────

async def _analyze_scope_with_claude(project_description: str) -> dict:
    """Use Claude to analyze project scope and recommend team + hours."""
    try:
        max_retries = 5
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
                        "max_tokens": 1500,
                        "system": """You are an expert software project estimator.
Analyze the project description and estimate the required team and hours.

Available role IDs: pm, tech_lead, backend_dev, frontend_dev, mobile_dev, ml_engineer, designer, qa, devops

Respond ONLY with a valid JSON object:
{
    "estimated_weeks": <number>,
    "roles": [
        {"role_id": "<role_id>", "hours": <number>, "justification": "brief reason"}
    ],
    "assumptions": ["list of key assumptions"],
    "risks": ["cost risks to flag"]
}

Be realistic. Not every project needs every role. A simple web app might need
4-5 roles while a complex ML platform might need 7-8.
Do NOT include markdown backticks. Return ONLY the JSON.""",
                        "messages": [{"role": "user", "content": f"Estimate this project:\n{project_description}"}],
                    },
                )

                if response.status_code == 429:
                    import asyncio
                    await asyncio.sleep((attempt + 1) * 15)
                    continue

                response.raise_for_status()
                data = response.json()
                return json.loads(data["content"][0]["text"].strip())
    except Exception:
        # Fallback: return a generic medium estimate
        return {
            "estimated_weeks": 12,
            "roles": [
                {"role_id": "pm", "hours": 60, "justification": "Project coordination"},
                {"role_id": "tech_lead", "hours": 80, "justification": "Architecture"},
                {"role_id": "backend_dev", "hours": 300, "justification": "Core development"},
                {"role_id": "frontend_dev", "hours": 250, "justification": "UI implementation"},
                {"role_id": "qa", "hours": 100, "justification": "Testing"},
                {"role_id": "devops", "hours": 60, "justification": "Deployment"},
            ],
            "assumptions": ["Fallback estimate — Claude analysis unavailable"],
            "risks": ["Estimate may not reflect actual project scope"],
        }


# ── Tool: Estimate Full Project ────────────────────────────────────

async def estimate_project(
    project_description: str,
    duration_weeks: int | None = None,
    complexity: Complexity = Complexity.MEDIUM,
    discount_tier: DiscountTier = DiscountTier.STANDARD,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Generate a full project cost estimation.

    1. Claude analyzes scope → recommends team + hours
    2. Apply complexity multiplier
    3. Calculate costs per role and phase
    4. Apply discount if applicable
    """
    try:
        rate_card = _load_rate_card()
        multiplier = rate_card["complexity_multipliers"].get(complexity.value, 1.0)
        discount_pct = _get_discount(rate_card, discount_tier)

        # Step 1: Claude analyzes scope
        analysis = await _analyze_scope_with_claude(project_description)
        weeks = duration_weeks or analysis.get("estimated_weeks", 12)

        # Step 2: Build role estimates with complexity multiplier
        role_estimates = []
        total_hours = 0
        total_cost = 0.0

        for role_entry in analysis.get("roles", []):
            role_id = role_entry["role_id"]
            base_hours = role_entry["hours"]
            adjusted_hours = math.ceil(base_hours * multiplier)

            role_info = _get_role(rate_card, role_id)
            if role_info:
                rate = role_info["hourly_rate"]
                title = role_info["title"]
            else:
                rate = 80  # default
                title = role_id.replace("_", " ").title()

            subtotal = adjusted_hours * rate
            total_hours += adjusted_hours
            total_cost += subtotal

            role_estimates.append(RoleEstimate(
                role_id=role_id,
                title=title,
                hours=adjusted_hours,
                hourly_rate=rate,
                subtotal=subtotal,
            ))

        # Step 3: Phase breakdown
        phase_estimates = []
        for phase_key, phase_info in rate_card.get("phase_distribution", {}).items():
            pct = phase_info["pct_of_total"]
            phase_hours = math.ceil(total_hours * pct / 100)
            phase_cost = total_cost * pct / 100

            phase_estimates.append(PhaseEstimate(
                phase=phase_key.replace("_", " ").title(),
                description=phase_info["description"],
                pct_of_total=pct,
                hours=phase_hours,
                cost=round(phase_cost, 2),
            ))

        # Step 4: Apply discount
        discount_amount = total_cost * discount_pct / 100
        cost_after_discount = round(total_cost - discount_amount, 2)

        estimate = ProjectEstimate(
            total_hours=total_hours,
            total_cost=round(total_cost, 2),
            cost_after_discount=cost_after_discount,
            discount_pct=discount_pct,
            complexity=complexity.value,
            duration_weeks=weeks,
            roles=role_estimates,
            phases=phase_estimates,
        )

        if response_format == ResponseFormat.JSON:
            result = estimate.model_dump()
            result["assumptions"] = analysis.get("assumptions", [])
            result["risks"] = analysis.get("risks", [])
            return format_json_response(result)

        # Markdown
        md = "# 💰 Project Cost Estimation\n\n"
        md += f"**Complexity:** {complexity.value.replace('_', ' ').title()} (×{multiplier})\n"
        md += f"**Duration:** {weeks} weeks\n"
        md += f"**Total Hours:** {total_hours:,}h\n\n"

        # Role breakdown table
        md += "## Team & Cost Breakdown\n\n"
        md += "| Role | Hours | Rate/h | Subtotal |\n"
        md += "|------|-------|--------|----------|\n"
        for r in role_estimates:
            md += f"| {r.title} | {r.hours:,}h | €{r.hourly_rate} | €{r.subtotal:,.0f} |\n"
        md += f"| **TOTAL** | **{total_hours:,}h** | | **€{total_cost:,.0f}** |\n\n"

        # Discount
        if discount_pct > 0:
            md += f"**Discount ({discount_tier.value}):** -{discount_pct}% → **€{cost_after_discount:,.0f}**\n\n"

        # Phase breakdown
        md += "## Phase Distribution\n\n"
        md += "| Phase | % | Hours | Cost |\n"
        md += "|-------|---|-------|------|\n"
        for p in phase_estimates:
            md += f"| {p.phase} | {p.pct_of_total}% | {p.hours:,}h | €{p.cost:,.0f} |\n"

        # Assumptions & risks
        assumptions = analysis.get("assumptions", [])
        risks = analysis.get("risks", [])
        if assumptions:
            md += "\n## 📌 Assumptions\n"
            for a in assumptions:
                md += f"- {a}\n"
        if risks:
            md += "\n## ⚠️ Cost Risks\n"
            for r in risks:
                md += f"- {r}\n"

        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Estimate from Custom Roles ───────────────────────────────

async def estimate_from_roles(
    roles: list[dict],
    discount_tier: DiscountTier = DiscountTier.STANDARD,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Calculate cost from a manually defined team composition."""
    try:
        rate_card = _load_rate_card()
        discount_pct = _get_discount(rate_card, discount_tier)

        role_estimates = []
        total_hours = 0
        total_cost = 0.0

        for entry in roles:
            role_id = entry.get("role_id", "custom")
            hours = entry.get("hours", 0)

            if role_id == "custom":
                title = entry.get("title", "Custom Role")
                rate = entry.get("hourly_rate", 80)
            else:
                role_info = _get_role(rate_card, role_id)
                if role_info:
                    title = role_info["title"]
                    rate = role_info["hourly_rate"]
                else:
                    title = role_id.replace("_", " ").title()
                    rate = 80

            subtotal = hours * rate
            total_hours += hours
            total_cost += subtotal

            role_estimates.append(RoleEstimate(
                role_id=role_id,
                title=title,
                hours=hours,
                hourly_rate=rate,
                subtotal=subtotal,
            ))

        discount_amount = total_cost * discount_pct / 100
        cost_after_discount = round(total_cost - discount_amount, 2)

        if response_format == ResponseFormat.JSON:
            return format_json_response({
                "total_hours": total_hours,
                "total_cost": round(total_cost, 2),
                "cost_after_discount": cost_after_discount,
                "discount_pct": discount_pct,
                "roles": [r.model_dump() for r in role_estimates],
                "currency": "EUR",
            })

        # Markdown
        md = "# 💰 Custom Team Estimation\n\n"
        md += "| Role | Hours | Rate/h | Subtotal |\n"
        md += "|------|-------|--------|----------|\n"
        for r in role_estimates:
            md += f"| {r.title} | {r.hours:,}h | €{r.hourly_rate} | €{r.subtotal:,.0f} |\n"
        md += f"| **TOTAL** | **{total_hours:,}h** | | **€{total_cost:,.0f}** |\n\n"

        if discount_pct > 0:
            md += f"**Discount ({discount_tier.value}):** -{discount_pct}% → **€{cost_after_discount:,.0f}**\n"

        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Get Rate Card ────────────────────────────────────────────

async def get_rate_card(
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Return the current rate card with all roles and pricing."""
    try:
        rate_card = _load_rate_card()

        if response_format == ResponseFormat.JSON:
            return format_json_response(rate_card)

        # Markdown
        md = "# 📊 Current Rate Card\n\n"
        md += f"**Currency:** {rate_card['currency']}\n\n"

        md += "## Roles & Rates\n\n"
        md += "| Role | Rate/h | Typical Allocation | Description |\n"
        md += "|------|--------|--------------------|-------------|\n"
        for r in rate_card["roles"]:
            md += f"| {r['title']} | €{r['hourly_rate']} | {r['typical_allocation_pct']}% | {r['description']} |\n"

        md += "\n## Complexity Multipliers\n\n"
        md += "| Level | Multiplier |\n"
        md += "|-------|------------|\n"
        for level, mult in rate_card["complexity_multipliers"].items():
            md += f"| {level.replace('_', ' ').title()} | ×{mult} |\n"

        md += "\n## Discount Tiers\n\n"
        md += "| Tier | Discount |\n"
        md += "|------|----------|\n"
        for tier, pct in rate_card["discount_tiers"].items():
            md += f"| {tier.replace('_', ' ').title()} | {pct}% |\n"

        return md

    except Exception as e:
        return handle_api_error(e)