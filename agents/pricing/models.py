"""Pydantic models for the Pricing Agent."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from enum import Enum


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class Complexity(str, Enum):
    """Project complexity level."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class DiscountTier(str, Enum):
    """Discount tier for pricing."""
    STANDARD = "standard"
    LONG_TERM = "long_term"
    STRATEGIC = "strategic"


# ── Tool Input Models ──────────────────────────────────────────────

class EstimateProjectInput(BaseModel):
    """Input for generating a full project cost estimation."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    project_description: str = Field(
        ...,
        description="Description of the project scope and requirements",
        min_length=10,
    )
    duration_weeks: Optional[int] = Field(
        default=None,
        description="Estimated duration in weeks (if known). AI will estimate if not provided.",
        ge=2,
        le=104,
    )
    complexity: Complexity = Field(
        default=Complexity.MEDIUM,
        description="Project complexity: 'low', 'medium', 'high', 'very_high'",
    )
    discount_tier: DiscountTier = Field(
        default=DiscountTier.STANDARD,
        description="Discount tier: 'standard' (0%), 'long_term' (5%), 'strategic' (10%)",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class EstimateFromRolesInput(BaseModel):
    """Input for estimating cost from a custom team composition."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    roles: list[dict] = Field(
        ...,
        description=(
            "List of roles with hours. Each dict: "
            "{'role_id': 'backend_dev', 'hours': 200} or "
            "{'role_id': 'custom', 'title': 'Data Scientist', 'hourly_rate': 90, 'hours': 100}"
        ),
        min_length=1,
    )
    discount_tier: DiscountTier = Field(
        default=DiscountTier.STANDARD,
        description="Discount tier: 'standard', 'long_term', 'strategic'",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


class GetRateCardInput(BaseModel):
    """Input for retrieving the current rate card."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' or 'json'",
    )


# ── Data Models ────────────────────────────────────────────────────

class RoleEstimate(BaseModel):
    """Cost estimate for a single role."""
    role_id: str
    title: str
    hours: int
    hourly_rate: int
    subtotal: float


class PhaseEstimate(BaseModel):
    """Cost estimate for a project phase."""
    phase: str
    description: str
    pct_of_total: int
    hours: int
    cost: float


class ProjectEstimate(BaseModel):
    """Complete project cost estimation."""
    total_hours: int
    total_cost: float
    cost_after_discount: float
    discount_pct: int
    complexity: str
    duration_weeks: int
    roles: list[RoleEstimate]
    phases: list[PhaseEstimate]
    currency: str = "EUR"
