"""Pydantic models for the Proposal Writer Agent."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum


class OutputFormat(str, Enum):
    """Output format for generated proposals."""
    MARKDOWN = "markdown"
    JSON = "json"


class ProposalLanguage(str, Enum):
    """Language for the proposal."""
    ENGLISH = "en"
    SPANISH = "es"


# ── Tool Input Models ──────────────────────────────────────────────

class GenerateProposalInput(BaseModel):
    """Input for generating a full technical/commercial proposal."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    client_name: str = Field(
        ...,
        description="Name of the client company",
        min_length=1,
        max_length=200,
    )
    project_description: str = Field(
        ...,
        description="Description of what the client needs (from RFP analysis or user input)",
        min_length=10,
    )
    client_research: Optional[str] = Field(
        default=None,
        description="Client research results (company profile, sector, size, etc.)",
    )
    relevant_projects: Optional[str] = Field(
        default=None,
        description="Similar past projects from the knowledge base to reference",
    )
    pricing_info: Optional[str] = Field(
        default=None,
        description="Pricing/budget estimation from the pricing agent",
    )
    language: ProposalLanguage = Field(
        default=ProposalLanguage.ENGLISH,
        description="Language for the proposal: 'en' or 'es'",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GenerateTimelineInput(BaseModel):
    """Input for generating a project timeline with phases."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    project_description: str = Field(
        ...,
        description="Description of the project scope",
        min_length=10,
    )
    total_weeks: Optional[int] = Field(
        default=None,
        description="Desired total duration in weeks (if not set, AI will estimate)",
        ge=2,
        le=104,
    )
    language: ProposalLanguage = Field(
        default=ProposalLanguage.ENGLISH,
        description="Language: 'en' or 'es'",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GenerateExecutiveSummaryInput(BaseModel):
    """Input for generating an executive summary from a full proposal."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    full_proposal: str = Field(
        ...,
        description="The full proposal text to summarize",
        min_length=50,
    )
    max_words: int = Field(
        default=300,
        description="Maximum word count for the summary",
        ge=50,
        le=1000,
    )
    language: ProposalLanguage = Field(
        default=ProposalLanguage.ENGLISH,
        description="Language: 'en' or 'es'",
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class ExportProposalDocxInput(BaseModel):
    """Input for exporting a proposal to DOCX format."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    proposal_markdown: str = Field(
        ...,
        description="The full proposal in markdown format (output from generate_proposal)",
        min_length=50,
    )
    client_name: str = Field(
        ...,
        description="Client company name (used in cover page and headers)",
        min_length=1,
        max_length=200,
    )
    project_title: str = Field(
        default="Technical Proposal",
        description="Title for the cover page",
        max_length=300,
    )
    company_name: str = Field(
        default="AZA FUTURE",
        description="Your company name for branding on cover page and headers",
        max_length=200,
    )


# ── Data Models ────────────────────────────────────────────────────

class ProposalSection(BaseModel):
    """A single section of a proposal."""
    title: str
    content: str
    order: int


class ProposalDocument(BaseModel):
    """Complete proposal structure."""
    client_name: str
    project_title: str
    sections: list[ProposalSection]
    generated_at: str
    language: str
    version: str = "1.0"


class TimelinePhase(BaseModel):
    """A phase in the project timeline."""
    phase_number: int
    name: str
    description: str
    duration_weeks: int
    deliverables: list[str]
    dependencies: list[int] = Field(default_factory=list)


class ProjectTimeline(BaseModel):
    """Complete project timeline."""
    total_weeks: int
    phases: list[TimelinePhase]
