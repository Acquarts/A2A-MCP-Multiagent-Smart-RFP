"""Tool implementations for the Client Research Agent.

Contains the business logic for each tool, separated from the MCP server
definition for testability and reusability.
"""

import json
import httpx
from typing import Any

from config.settings import settings
from shared.utils import format_json_response, handle_api_error
from agents.client_research.models import (
    CompanyProfile,
    RFPAnalysis,
    ResponseFormat,
)

# ── Constants ──────────────────────────────────────────────────────

TAVILY_API_URL = "https://api.tavily.com/search"
TAVILY_TIMEOUT = 30.0

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_TIMEOUT = 60.0


# ── Tavily Web Search ──────────────────────────────────────────────

async def search_web(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """Search the web using Tavily API."""
    async with httpx.AsyncClient(timeout=TAVILY_TIMEOUT) as client:
        response = await client.post(
            TAVILY_API_URL,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": True,
                "include_raw_content": False,
                "search_depth": "advanced",
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", []), data.get("answer", "")


# ── Claude Analysis ────────────────────────────────────────────────

async def analyze_with_claude(system_prompt: str, user_content: str) -> str:
    """Send content to Claude for analysis with retry on rate limits."""
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
                    "max_tokens": 2000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_content}],
                },
            )
            if response.status_code == 429:
                import asyncio
                wait_time = (attempt + 1) * 15
                await asyncio.sleep(wait_time)
                continue
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]
    raise RuntimeError("Claude API rate limit exceeded in client research after all retries.")


# ── Tool: Search Company Info ──────────────────────────────────────

async def search_company_info(
    company_name: str,
    additional_context: str | None = None,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Research a company using web search + Claude analysis.

    1. Searches the web for company info via Tavily
    2. Sends results to Claude for structured extraction
    3. Returns a CompanyProfile
    """
    try:
        # Build search query
        query = f"{company_name} company info sector size funding"
        if additional_context:
            query += f" {additional_context}"

        # Search web
        results, tavily_answer = await search_web(query, max_results=5)

        if not results and not tavily_answer:
            return format_json_response({
                "error": f"No results found for '{company_name}'",
                "suggestion": "Try adding more context about the company",
            })

        # Prepare context for Claude
        search_context = f"Tavily summary: {tavily_answer}\n\n"
        for i, r in enumerate(results, 1):
            search_context += f"Source {i}: {r.get('title', 'N/A')}\n"
            search_context += f"URL: {r.get('url', 'N/A')}\n"
            search_context += f"Content: {r.get('content', 'N/A')}\n\n"

        # Analyze with Claude
        system_prompt = """You are a business research analyst. Extract structured company 
information from search results. Respond ONLY with a valid JSON object matching this schema:
{
    "name": "string",
    "sector": "string or null",
    "description": "brief company description",
    "size": "estimated employee count/range or null",
    "location": "headquarters location or null",
    "website": "main website URL or null",
    "funding": "funding info or null",
    "technologies": ["list of technologies they use or offer"],
    "key_people": ["CEO: Name", "CTO: Name"],
    "recent_news": ["brief news items"]
}
Do NOT include markdown backticks. Return ONLY the JSON object."""

        claude_response = await analyze_with_claude(
            system_prompt,
            f"Research this company: {company_name}\n\nSearch results:\n{search_context}",
        )

        # Parse Claude's response into CompanyProfile
        profile_data = json.loads(claude_response.strip())
        profile = CompanyProfile(**profile_data)

        if response_format == ResponseFormat.JSON:
            return format_json_response(profile.model_dump())

        # Markdown format
        md = f"# 🏢 {profile.name}\n\n"
        if profile.description:
            md += f"{profile.description}\n\n"
        if profile.sector:
            md += f"**Sector:** {profile.sector}\n"
        if profile.size:
            md += f"**Size:** {profile.size}\n"
        if profile.location:
            md += f"**Location:** {profile.location}\n"
        if profile.website:
            md += f"**Website:** {profile.website}\n"
        if profile.funding:
            md += f"**Funding:** {profile.funding}\n"
        if profile.technologies:
            md += f"\n**Technologies:** {', '.join(profile.technologies)}\n"
        if profile.key_people:
            md += "\n**Key People:**\n"
            for person in profile.key_people:
                md += f"- {person}\n"
        if profile.recent_news:
            md += "\n**Recent News:**\n"
            for news in profile.recent_news:
                md += f"- {news}\n"

        return md

    except json.JSONDecodeError:
        return format_json_response({
            "error": "Failed to parse company analysis",
            "raw_response": claude_response[:500],
        })
    except Exception as e:
        return handle_api_error(e)


# ── Tool: Analyze RFP Document ─────────────────────────────────────

async def analyze_rfp_document(
    rfp_text: str,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Analyze an RFP document using Claude to extract key information.

    Extracts: requirements, technical specs, budget indicators,
    timeline, evaluation criteria, and risks.
    """
    try:
        system_prompt = """You are an expert proposal analyst. Analyze the RFP document and 
extract structured information. Respond ONLY with a valid JSON object matching this schema:
{
    "project_summary": "2-3 sentence summary of what the client needs",
    "key_requirements": ["list of main business requirements"],
    "technical_requirements": ["list of technical requirements"],
    "budget_indicators": "any budget mentions or constraints, or null",
    "timeline_indicators": "any timeline/deadline info, or null",
    "evaluation_criteria": ["how proposals will be evaluated"],
    "risks_and_concerns": ["potential risks or red flags"]
}
Do NOT include markdown backticks. Return ONLY the JSON object."""

        claude_response = await analyze_with_claude(
            system_prompt,
            f"Analyze this RFP document:\n\n{rfp_text}",
        )

        analysis_data = json.loads(claude_response.strip())
        analysis = RFPAnalysis(**analysis_data)

        if response_format == ResponseFormat.JSON:
            return format_json_response(analysis.model_dump())

        # Markdown format
        md = "# 📋 RFP Analysis\n\n"
        md += f"## Summary\n{analysis.project_summary}\n\n"

        if analysis.key_requirements:
            md += "## Key Requirements\n"
            for req in analysis.key_requirements:
                md += f"- {req}\n"
            md += "\n"

        if analysis.technical_requirements:
            md += "## Technical Requirements\n"
            for req in analysis.technical_requirements:
                md += f"- {req}\n"
            md += "\n"

        if analysis.budget_indicators:
            md += f"## Budget\n{analysis.budget_indicators}\n\n"

        if analysis.timeline_indicators:
            md += f"## Timeline\n{analysis.timeline_indicators}\n\n"

        if analysis.evaluation_criteria:
            md += "## Evaluation Criteria\n"
            for criteria in analysis.evaluation_criteria:
                md += f"- {criteria}\n"
            md += "\n"

        if analysis.risks_and_concerns:
            md += "## ⚠️ Risks & Concerns\n"
            for risk in analysis.risks_and_concerns:
                md += f"- {risk}\n"

        return md

    except json.JSONDecodeError:
        return format_json_response({
            "error": "Failed to parse RFP analysis",
            "raw_response": claude_response[:500],
        })
    except Exception as e:
        return handle_api_error(e)


# ── Tool: Search LinkedIn ──────────────────────────────────────────

async def search_linkedin_company(
    company_name: str,
    find_decision_makers: bool = True,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Search for company info on LinkedIn using web search as proxy.

    Note: Uses Tavily to search LinkedIn pages since direct LinkedIn API
    requires OAuth and company page admin access. This approach gets
    publicly available LinkedIn information.
    """
    try:
        # Search LinkedIn pages via Tavily
        queries = [
            f"site:linkedin.com/company {company_name}",
        ]
        if find_decision_makers:
            queries.append(
                f"site:linkedin.com/in {company_name} CTO OR CEO OR 'VP Engineering' OR Director"
            )

        all_results = []
        for query in queries:
            results, _ = await search_web(query, max_results=5)
            all_results.extend(results)

        if not all_results:
            return format_json_response({
                "error": f"No LinkedIn results found for '{company_name}'",
                "suggestion": "Try the search_company_info tool for general web results",
            })

        # Prepare context for Claude
        search_context = ""
        for i, r in enumerate(all_results, 1):
            search_context += f"Result {i}: {r.get('title', 'N/A')}\n"
            search_context += f"URL: {r.get('url', 'N/A')}\n"
            search_context += f"Content: {r.get('content', 'N/A')}\n\n"

        system_prompt = """You are a business intelligence analyst. From LinkedIn search results, 
extract company and people information. Respond ONLY with a valid JSON object:
{
    "company_linkedin_url": "LinkedIn company page URL or null",
    "company_summary": "brief description from LinkedIn or null",
    "employee_count": "estimated from LinkedIn or null",
    "industry": "industry from LinkedIn or null",
    "decision_makers": [
        {"name": "Full Name", "role": "Title", "linkedin_url": "URL or null"}
    ],
    "insights": ["any useful insights from LinkedIn presence"]
}
Do NOT include markdown backticks. Return ONLY the JSON object."""

        claude_response = await analyze_with_claude(
            system_prompt,
            f"Extract LinkedIn info for: {company_name}\n\nSearch results:\n{search_context}",
        )

        data = json.loads(claude_response.strip())

        if response_format == ResponseFormat.JSON:
            return format_json_response(data)

        # Markdown format
        md = f"# 🔗 LinkedIn Research: {company_name}\n\n"
        if data.get("company_linkedin_url"):
            md += f"**Profile:** {data['company_linkedin_url']}\n"
        if data.get("company_summary"):
            md += f"**About:** {data['company_summary']}\n"
        if data.get("employee_count"):
            md += f"**Employees:** {data['employee_count']}\n"
        if data.get("industry"):
            md += f"**Industry:** {data['industry']}\n"

        if data.get("decision_makers"):
            md += "\n## 👤 Decision Makers\n"
            for person in data["decision_makers"]:
                md += f"- **{person.get('name', 'N/A')}** — {person.get('role', 'N/A')}"
                if person.get("linkedin_url"):
                    md += f" ([LinkedIn]({person['linkedin_url']}))"
                md += "\n"

        if data.get("insights"):
            md += "\n## 💡 Insights\n"
            for insight in data["insights"]:
                md += f"- {insight}\n"

        return md

    except json.JSONDecodeError:
        return format_json_response({
            "error": "Failed to parse LinkedIn analysis",
            "raw_response": claude_response[:500],
        })
    except Exception as e:
        return handle_api_error(e)