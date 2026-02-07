"""Pydantic models for the Knowledge Base Agent."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ── Tool Input Models ──────────────────────────────────────────────

class SearchProjectsInput(BaseModel):
    """Input for searching past projects by keywords or requirements."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search query describing the kind of project to find (e.g., 'mobile app with AI recommendations', 'e-commerce platform')",
        min_length=2,
        max_length=500,
    )
    sector: Optional[str] = Field(
        default=None,
        description="Filter by sector (e.g., 'Fintech', 'Healthcare', 'E-commerce')",
    )
    max_results: int = Field(
        default=3,
        description="Maximum number of projects to return",
        ge=1,
        le=10,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GetProjectDetailsInput(BaseModel):
    """Input for getting full details of a specific project."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    project_id: str = Field(
        ...,
        description="Project ID to retrieve (e.g., 'PRJ-001')",
        min_length=1,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class SearchTechStackInput(BaseModel):
    """Input for finding projects by technology stack."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    technologies: list[str] = Field(
        ...,
        description="List of technologies to search for (e.g., ['React', 'Python', 'AWS'])",
        min_length=1,
        max_length=10,
    )
    match_all: bool = Field(
        default=False,
        description="If True, project must use ALL listed technologies. If False, any match counts.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GetCaseStudiesInput(BaseModel):
    """Input for retrieving case studies relevant to a proposal."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    client_sector: str = Field(
        ...,
        description="The target client's sector to find relevant case studies (e.g., 'Food & Delivery')",
        min_length=2,
    )
    project_type: Optional[str] = Field(
        default=None,
        description="Type of project (e.g., 'mobile app', 'dashboard', 'platform')",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


# ── Data Models ────────────────────────────────────────────────────

class ProjectSummary(BaseModel):
    """Lightweight project info for search results."""
    project_id: str
    name: str
    client: str
    sector: str
    description: str
    tech_stack: list[str]
    year: int
    relevance_score: float = Field(default=0.0, description="Search relevance 0.0-1.0")


class ProjectDetail(BaseModel):
    """Full project information."""
    project_id: str
    name: str
    client: str
    sector: str
    description: str
    tech_stack: list[str]
    team_size: int
    duration_weeks: int
    total_hours: int
    budget_eur: int
    year: int
    status: str
    outcome: str
    key_features: list[str]
    challenges: list[str]
    tags: list[str]
