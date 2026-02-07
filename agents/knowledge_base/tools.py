"""Tool implementations for the Knowledge Base Agent.

Uses a JSON-based project store with keyword + AI-powered relevance scoring.
Can be upgraded to a vector database (ChromaDB, Pinecone) for semantic search.
"""

import json
import os
from typing import Any
from pathlib import Path

import httpx

from config.settings import settings
from shared.utils import format_json_response, handle_api_error
from agents.knowledge_base.models import (
    ResponseFormat,
    ProjectSummary,
    ProjectDetail,
)

# ── Constants ──────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
PROJECTS_FILE = DATA_DIR / "projects.json"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_TIMEOUT = 60.0


# ── Data Layer ─────────────────────────────────────────────────────

def _load_projects() -> list[dict[str, Any]]:
    """Load projects from the JSON knowledge base."""
    if not PROJECTS_FILE.exists():
        return []
    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _keyword_score(project: dict, query_terms: list[str]) -> float:
    """Calculate a basic keyword relevance score (0.0 - 1.0).

    Searches across name, description, tags, tech_stack, sector,
    and key_features for matching terms.
    """
    searchable_text = " ".join([
        project.get("name", ""),
        project.get("description", ""),
        project.get("sector", ""),
        project.get("outcome", ""),
        " ".join(project.get("tags", [])),
        " ".join(project.get("tech_stack", [])),
        " ".join(project.get("key_features", [])),
    ]).lower()

    if not query_terms:
        return 0.0

    matches = sum(1 for term in query_terms if term.lower() in searchable_text)
    return round(matches / len(query_terms), 2)


async def _rank_with_claude(query: str, projects: list[dict]) -> list[dict]:
    """Use Claude to semantically rank projects by relevance to query."""
    if not projects:
        return []

    summaries = []
    for p in projects:
        summaries.append({
            "project_id": p["project_id"],
            "name": p["name"],
            "sector": p["sector"],
            "description": p["description"],
            "tags": p.get("tags", []),
        })

    try:
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
                    "max_tokens": 1000,
                    "system": (
                        "You are a project matching engine. Given a query and a list of projects, "
                        "return a JSON array of project_ids sorted by relevance (most relevant first). "
                        "Include a relevance_score (0.0 to 1.0) for each. "
                        "Respond ONLY with a JSON array like: "
                        '[{"project_id": "PRJ-001", "relevance_score": 0.95}]. '
                        "No markdown backticks."
                    ),
                    "messages": [{
                        "role": "user",
                        "content": f"Query: {query}\n\nProjects:\n{json.dumps(summaries, indent=2)}",
                    }],
                },
            )
            response.raise_for_status()
            data = response.json()
            rankings = json.loads(data["content"][0]["text"].strip())

            # Map scores back to projects
            score_map = {r["project_id"]: r["relevance_score"] for r in rankings}
            for p in projects:
                p["_relevance"] = score_map.get(p["project_id"], 0.0)

            return sorted(projects, key=lambda x: x.get("_relevance", 0), reverse=True)

    except Exception:
        # Fallback: return as-is if Claude ranking fails
        return projects


# ── Tool: Search Past Projects ─────────────────────────────────────

async def search_past_projects(
    query: str,
    sector: str | None = None,
    max_results: int = 3,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Search internal projects by query with optional sector filter.

    Uses keyword matching for initial filtering, then Claude for
    semantic ranking of results.
    """
    try:
        projects = _load_projects()
        if not projects:
            return format_json_response({
                "error": "Knowledge base is empty",
                "suggestion": "Add projects to agents/knowledge_base/data/projects.json",
            })

        # Filter by sector if provided
        if sector:
            sector_lower = sector.lower()
            projects = [
                p for p in projects
                if sector_lower in p.get("sector", "").lower()
            ]

        # Keyword pre-filter
        query_terms = [t.strip() for t in query.lower().split() if len(t.strip()) > 2]
        for p in projects:
            p["_keyword_score"] = _keyword_score(p, query_terms)

        # Keep projects with any keyword match, or all if none match
        matched = [p for p in projects if p["_keyword_score"] > 0]
        candidates = matched if matched else projects

        # Rank with Claude for semantic relevance
        ranked = await _rank_with_claude(query, candidates)
        top_results = ranked[:max_results]

        if not top_results:
            return format_json_response({
                "message": "No matching projects found",
                "query": query,
                "suggestion": "Try broader search terms",
            })

        # Build response
        summaries = []
        for p in top_results:
            summaries.append(ProjectSummary(
                project_id=p["project_id"],
                name=p["name"],
                client=p["client"],
                sector=p.get("sector", "N/A"),
                description=p["description"],
                tech_stack=p.get("tech_stack", []),
                year=p.get("year", 0),
                relevance_score=p.get("_relevance", p.get("_keyword_score", 0)),
            ))

        if response_format == ResponseFormat.JSON:
            return format_json_response({
                "query": query,
                "total_found": len(top_results),
                "projects": [s.model_dump() for s in summaries],
            })

        # Markdown
        md = f"# 🔍 Projects matching: \"{query}\"\n\n"
        md += f"Found **{len(summaries)}** relevant project(s):\n\n"
        for s in summaries:
            score_pct = int(s.relevance_score * 100)
            md += f"---\n### {s.name} ({s.project_id})\n"
            md += f"**Client:** {s.client} | **Sector:** {s.sector} | **Year:** {s.year}\n"
            md += f"**Relevance:** {score_pct}%\n\n"
            md += f"{s.description}\n\n"
            md += f"**Tech:** {', '.join(s.tech_stack)}\n\n"

        md += "\n💡 Use `get_project_details` with a project ID for full information."
        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Get Project Details ──────────────────────────────────────

async def get_project_details(
    project_id: str,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Get full details of a specific project by its ID."""
    try:
        projects = _load_projects()
        project = next(
            (p for p in projects if p["project_id"].upper() == project_id.upper()),
            None,
        )

        if not project:
            available = [p["project_id"] for p in projects]
            return format_json_response({
                "error": f"Project '{project_id}' not found",
                "available_ids": available,
            })

        detail = ProjectDetail(**project)

        if response_format == ResponseFormat.JSON:
            return format_json_response(detail.model_dump())

        # Markdown
        md = f"# 📋 {detail.name}\n\n"
        md += f"**ID:** {detail.project_id} | **Status:** {detail.status}\n"
        md += f"**Client:** {detail.client} | **Sector:** {detail.sector} | **Year:** {detail.year}\n\n"
        md += f"## Description\n{detail.description}\n\n"
        md += f"## Metrics\n"
        md += f"- **Team Size:** {detail.team_size} people\n"
        md += f"- **Duration:** {detail.duration_weeks} weeks\n"
        md += f"- **Total Hours:** {detail.total_hours:,}h\n"
        md += f"- **Budget:** €{detail.budget_eur:,}\n\n"
        md += f"## Outcome\n{detail.outcome}\n\n"
        md += f"## Key Features\n"
        for feat in detail.key_features:
            md += f"- {feat}\n"
        md += f"\n## Tech Stack\n{', '.join(detail.tech_stack)}\n\n"
        md += f"## Challenges\n"
        for ch in detail.challenges:
            md += f"- {ch}\n"

        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Search by Tech Stack ─────────────────────────────────────

async def search_tech_stack(
    technologies: list[str],
    match_all: bool = False,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Find projects that use specific technologies."""
    try:
        projects = _load_projects()
        search_techs = {t.lower() for t in technologies}

        results = []
        for p in projects:
            project_techs = {t.lower() for t in p.get("tech_stack", [])}
            matched_techs = search_techs & project_techs

            if match_all and matched_techs == search_techs:
                results.append((p, len(matched_techs)))
            elif not match_all and matched_techs:
                results.append((p, len(matched_techs)))

        results.sort(key=lambda x: x[1], reverse=True)

        if not results:
            return format_json_response({
                "message": f"No projects found with technologies: {technologies}",
                "match_mode": "all" if match_all else "any",
            })

        if response_format == ResponseFormat.JSON:
            return format_json_response({
                "technologies_searched": technologies,
                "match_all": match_all,
                "results": [
                    {
                        "project_id": p["project_id"],
                        "name": p["name"],
                        "tech_stack": p["tech_stack"],
                        "matched_count": count,
                    }
                    for p, count in results
                ],
            })

        # Markdown
        mode = "ALL of" if match_all else "any of"
        md = f"# 🛠️ Projects using {mode}: {', '.join(technologies)}\n\n"
        for p, count in results:
            md += f"### {p['name']} ({p['project_id']})\n"
            md += f"**Matches:** {count}/{len(technologies)} technologies\n"
            md += f"**Full Stack:** {', '.join(p['tech_stack'])}\n\n"

        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Get Case Studies ─────────────────────────────────────────

async def get_case_studies(
    client_sector: str,
    project_type: str | None = None,
    response_format: ResponseFormat = ResponseFormat.MARKDOWN,
) -> str:
    """Find case studies relevant to a client's sector and project type.

    Returns completed projects with outcomes that can be used as
    social proof in a proposal.
    """
    try:
        query_parts = [client_sector]
        if project_type:
            query_parts.append(project_type)
        query = " ".join(query_parts)

        # Reuse search logic
        return await search_past_projects(
            query=query,
            max_results=3,
            response_format=response_format,
        )

    except Exception as e:
        return handle_api_error(e)