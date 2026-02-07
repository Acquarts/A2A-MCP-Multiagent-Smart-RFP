"""Tool implementations for the Proposal Writer Agent.

Uses Claude to generate professional proposals based on a structured
template, client research, and internal project knowledge.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from config.settings import settings
from shared.utils import format_json_response, handle_api_error
from agents.proposal_writer.models import (
    OutputFormat,
    ProposalLanguage,
    ProposalDocument,
    ProposalSection,
    ProjectTimeline,
    TimelinePhase,
)

# ── Constants ──────────────────────────────────────────────────────

TEMPLATES_DIR = Path(__file__).parent / "templates"
PROPOSAL_TEMPLATE = TEMPLATES_DIR / "proposal_structure.json"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
ANTHROPIC_TIMEOUT = 120.0


# ── Helpers ────────────────────────────────────────────────────────

def _load_template() -> list[dict[str, Any]]:
    """Load the proposal structure template."""
    with open(PROPOSAL_TEMPLATE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["sections"]


def _get_title(section: dict, language: ProposalLanguage) -> str:
    """Get section title in the correct language."""
    key = f"title_{language.value}"
    return section.get(key, section.get("title_en", "Section"))


async def _generate_with_claude(system_prompt: str, user_content: str, max_tokens: int = 3000) -> str:
    """Send content to Claude for generation with retry on rate limits."""
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
                    "max_tokens": max_tokens,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_content}],
                },
            )

            if response.status_code == 429:
                wait_time = (attempt + 1) * 15
                import asyncio
                await asyncio.sleep(wait_time)
                continue

            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"]

    raise RuntimeError("Claude API rate limit exceeded in proposal writer after all retries.")


# ── Tool: Generate Full Proposal ───────────────────────────────────

async def generate_proposal(
    client_name: str,
    project_description: str,
    client_research: str | None = None,
    relevant_projects: str | None = None,
    pricing_info: str | None = None,
    language: ProposalLanguage = ProposalLanguage.ENGLISH,
    output_format: OutputFormat = OutputFormat.MARKDOWN,
) -> str:
    """Generate a complete technical/commercial proposal.

    Builds each section using the template structure, enriched with
    client research and internal project data when available.
    """
    try:
        template_sections = _load_template()
        lang_name = "Spanish" if language == ProposalLanguage.SPANISH else "English"

        # Build context block with all available info
        context_parts = [f"Client: {client_name}", f"Project: {project_description}"]
        if client_research:
            context_parts.append(f"Client Research:\n{client_research}")
        if relevant_projects:
            context_parts.append(f"Relevant Past Projects:\n{relevant_projects}")
        if pricing_info:
            context_parts.append(f"Pricing Information:\n{pricing_info}")

        full_context = "\n\n---\n\n".join(context_parts)

        # Generate all sections in one Claude call for coherence
        sections_instructions = ""
        for i, section in enumerate(template_sections, 1):
            title = _get_title(section, language)
            sections_instructions += (
                f"\n## Section {i}: {title}\n"
                f"Instructions: {section['instruction']}\n"
            )

        system_prompt = f"""You are a professional proposal writer for a technology consultancy.
Write a compelling, detailed, and professional proposal in {lang_name}.

IMPORTANT RULES:
- Write in {lang_name} only
- Be specific and detailed, avoid generic filler text
- If client research is provided, reference specific facts about the client
- If past projects are provided, use them as case studies with real data
- If pricing info is provided, include it in the Investment section
- If any info is missing, write reasonable placeholder content marked with [TO COMPLETE]
- Use a professional but warm tone
- Each section should be substantial (at least 2-3 paragraphs)

Respond with the proposal sections separated by the exact marker: ---SECTION_BREAK---
Each section should start with its title as a markdown heading (##).
Do NOT include any other separators or markers."""

        user_content = (
            f"Generate a proposal with these sections:\n{sections_instructions}\n\n"
            f"Using this context:\n\n{full_context}"
        )

        claude_response = await _generate_with_claude(system_prompt, user_content, max_tokens=6000)

        # Parse sections from response
        raw_sections = claude_response.split("---SECTION_BREAK---")
        parsed_sections = []
        for i, raw in enumerate(raw_sections):
            content = raw.strip()
            if not content:
                continue

            title = _get_title(template_sections[i], language) if i < len(template_sections) else f"Section {i+1}"
            parsed_sections.append(ProposalSection(
                title=title,
                content=content,
                order=i + 1,
            ))

        proposal = ProposalDocument(
            client_name=client_name,
            project_title=f"Technical Proposal — {client_name}",
            sections=parsed_sections,
            generated_at=datetime.now(timezone.utc).isoformat(),
            language=language.value,
        )

        if output_format == OutputFormat.JSON:
            return format_json_response(proposal.model_dump())

        # Markdown
        md = f"# 📄 {proposal.project_title}\n\n"
        md += f"*Generated: {proposal.generated_at[:10]} | Language: {lang_name} | v{proposal.version}*\n\n"
        md += "---\n\n"
        for section in proposal.sections:
            md += f"{section.content}\n\n---\n\n"

        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Generate Timeline ────────────────────────────────────────

async def generate_timeline(
    project_description: str,
    total_weeks: int | None = None,
    language: ProposalLanguage = ProposalLanguage.ENGLISH,
    output_format: OutputFormat = OutputFormat.MARKDOWN,
) -> str:
    """Generate a project timeline with phases, durations, and deliverables."""
    try:
        lang_name = "Spanish" if language == ProposalLanguage.SPANISH else "English"
        weeks_instruction = (
            f"The total project duration should be approximately {total_weeks} weeks."
            if total_weeks
            else "Estimate a reasonable total duration based on project complexity."
        )

        system_prompt = f"""You are a project planning expert. Generate a detailed project timeline
in {lang_name}. {weeks_instruction}

Respond ONLY with a valid JSON object:
{{
    "total_weeks": <number>,
    "phases": [
        {{
            "phase_number": 1,
            "name": "Phase name",
            "description": "What happens in this phase",
            "duration_weeks": <number>,
            "deliverables": ["deliverable 1", "deliverable 2"],
            "dependencies": []
        }}
    ]
}}

Include typical phases: Discovery/Planning, Design, Development (split into sprints if >4 weeks),
Testing/QA, Deployment, and Post-launch Support.
Do NOT include markdown backticks. Return ONLY the JSON."""

        claude_response = await _generate_with_claude(
            system_prompt,
            f"Generate a timeline for:\n{project_description}",
        )

        data = json.loads(claude_response.strip())
        timeline = ProjectTimeline(**data)

        if output_format == OutputFormat.JSON:
            return format_json_response(timeline.model_dump())

        # Markdown Gantt-style
        md = "# 📅 Project Timeline\n\n"
        md += f"**Total Duration:** {timeline.total_weeks} weeks\n\n"
        md += "| Phase | Name | Duration | Deliverables |\n"
        md += "|-------|------|----------|-------------|\n"

        week_counter = 0
        for phase in timeline.phases:
            week_start = week_counter + 1
            week_end = week_counter + phase.duration_weeks
            week_counter = week_end
            deliverables = ", ".join(phase.deliverables[:3])
            md += f"| {phase.phase_number} | **{phase.name}** | W{week_start}-W{week_end} ({phase.duration_weeks}w) | {deliverables} |\n"

        md += "\n"
        for phase in timeline.phases:
            md += f"\n### Phase {phase.phase_number}: {phase.name}\n"
            md += f"{phase.description}\n\n"
            md += "**Deliverables:**\n"
            for d in phase.deliverables:
                md += f"- {d}\n"

        return md

    except json.JSONDecodeError:
        return format_json_response({
            "error": "Failed to parse timeline",
            "raw_response": claude_response[:500],
        })
    except Exception as e:
        return handle_api_error(e)


# ── Tool: Generate Executive Summary ───────────────────────────────

async def generate_executive_summary(
    full_proposal: str,
    max_words: int = 300,
    language: ProposalLanguage = ProposalLanguage.ENGLISH,
    output_format: OutputFormat = OutputFormat.MARKDOWN,
) -> str:
    """Generate a concise executive summary from a full proposal."""
    try:
        lang_name = "Spanish" if language == ProposalLanguage.SPANISH else "English"

        system_prompt = f"""You are an expert at writing executive summaries for technical proposals.
Write in {lang_name}. Maximum {max_words} words.

The summary must:
- Open with the client's core need
- Highlight the proposed solution and its key differentiators
- Mention relevant experience/track record
- Include expected outcomes or ROI
- End with a clear call to action

Be compelling and concise. Every sentence must earn its place."""

        claude_response = await _generate_with_claude(
            system_prompt,
            f"Write an executive summary for this proposal:\n\n{full_proposal}",
            max_tokens=1000,
        )

        if output_format == OutputFormat.JSON:
            return format_json_response({
                "executive_summary": claude_response.strip(),
                "language": language.value,
                "word_count": len(claude_response.split()),
            })

        md = "# 📋 Executive Summary\n\n"
        md += claude_response.strip()
        return md

    except Exception as e:
        return handle_api_error(e)


# ── Tool: Export Proposal to DOCX ──────────────────────────────────

async def export_proposal_docx(
    proposal_markdown: str,
    client_name: str,
    project_title: str = "Technical Proposal",
    company_name: str = "AZA FUTURE",
) -> str:
    """Export a markdown proposal to a professional DOCX file.

    Creates a Word document with cover page, styled headings,
    tables, bullet lists, headers/footers, and page numbers.
    """
    try:
        from shared.docx_exporter import export_proposal_to_docx

        output_path = export_proposal_to_docx(
            markdown_content=proposal_markdown,
            client_name=client_name,
            project_title=project_title,
            company_name=company_name,
        )

        abs_path = str(Path(output_path).resolve())

        return format_json_response({
            "status": "success",
            "message": "Proposal exported to DOCX successfully",
            "file_path": abs_path,
            "file_name": Path(output_path).name,
        })

    except ImportError:
        return format_json_response({
            "status": "error",
            "message": "python-docx is not installed. Run: pip install python-docx",
        })
    except Exception as e:
        return handle_api_error(e)