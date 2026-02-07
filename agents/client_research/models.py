"""Pydantic models for the Client Research Agent."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ── Tool Input Models ──────────────────────────────────────────────

class SearchCompanyInput(BaseModel):
    """Input for searching company information on the web."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(
        ...,
        description="Name of the company to research (e.g., 'Acme Corp', 'Stripe')",
        min_length=1,
        max_length=200,
    )
    additional_context: Optional[str] = Field(
        default=None,
        description="Extra context to refine the search (e.g., 'fintech startup in Madrid')",
        max_length=500,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for readable or 'json' for structured",
    )


class AnalyzeRFPInput(BaseModel):
    """Input for analyzing an RFP document text."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    rfp_text: str = Field(
        ...,
        description="Full text content of the RFP document to analyze",
        min_length=10,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for readable or 'json' for structured",
    )


class SearchLinkedInInput(BaseModel):
    """Input for searching company profiles on LinkedIn."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(
        ...,
        description="Company name to search on LinkedIn",
        min_length=1,
        max_length=200,
    )
    find_decision_makers: bool = Field(
        default=True,
        description="Whether to search for key decision makers (CTO, CEO, VP Engineering)",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for readable or 'json' for structured",
    )


# ── Data Models (outputs) ─────────────────────────────────────────

class CompanyProfile(BaseModel):
    """Structured company information."""
    name: str
    sector: Optional[str] = None
    description: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    website: Optional[str] = None
    funding: Optional[str] = None
    technologies: list[str] = Field(default_factory=list)
    key_people: list[str] = Field(default_factory=list)
    recent_news: list[str] = Field(default_factory=list)


class RFPAnalysis(BaseModel):
    """Structured RFP analysis result."""
    project_summary: str
    key_requirements: list[str] = Field(default_factory=list)
    technical_requirements: list[str] = Field(default_factory=list)
    budget_indicators: Optional[str] = None
    timeline_indicators: Optional[str] = None
    evaluation_criteria: list[str] = Field(default_factory=list)
    risks_and_concerns: list[str] = Field(default_factory=list)
