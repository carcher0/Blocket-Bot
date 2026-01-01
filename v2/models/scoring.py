"""
Scoring models - market stats, score breakdowns, and ranked results.
"""
from typing import Optional

from pydantic import BaseModel, Field

from .listing import NormalizedListing
from .enrichment import EnrichedListing


class MarketStats(BaseModel):
    """Statistics for a comparison group (comps)."""
    median: float = Field(description="Median price in the group")
    iqr: float = Field(description="Interquartile range")
    q1: float = Field(description="25th percentile")
    q3: float = Field(description="75th percentile")
    min_price: float
    max_price: float
    n: int = Field(description="Number of listings in group")
    
    # Metadata about the comp group
    comp_key: Optional[str] = Field(default=None, description="Key used for grouping")
    relaxation_level: int = Field(
        default=0,
        description="How many times grouping was relaxed to get enough comps"
    )
    is_sufficient: bool = Field(
        default=True,
        description="Whether we have enough comps for reliable stats"
    )


class ValueScore(BaseModel):
    """Score component based on price vs market."""
    score: float = Field(ge=0, le=100)
    asking_price: float
    expected_price: float = Field(description="Based on comps median")
    deal_delta: float = Field(description="Positive = below market, negative = above")
    deal_delta_percent: float = Field(description="Delta as percentage")
    explanation: str = Field(description="Human-readable explanation")


class PreferenceScore(BaseModel):
    """Score component based on preference matching."""
    score: float = Field(ge=0, le=100)
    matched_preferences: list[str] = Field(default_factory=list)
    unmatched_preferences: list[str] = Field(default_factory=list)
    missing_info_penalties: list[str] = Field(default_factory=list)
    explanation: str


class RiskScore(BaseModel):
    """Score component based on risk assessment."""
    score: float = Field(ge=0, le=100, description="Higher = less risky")
    risk_flags: list[str] = Field(default_factory=list)
    explanation: str


class ScoringBreakdown(BaseModel):
    """Complete scoring breakdown for a listing."""
    total: float = Field(ge=0, le=100, description="Final weighted score")
    
    # Component scores
    value_score: ValueScore
    preference_score: PreferenceScore
    risk_score: RiskScore
    
    # Weights used
    value_weight: float = Field(default=0.5)
    preference_weight: float = Field(default=0.35)
    risk_weight: float = Field(default=0.15)
    
    # Quick summary
    summary_explanation: str = Field(description="One-line summary of why this score")


class RankedListing(BaseModel):
    """A listing with its rank, scores, and all enrichment data."""
    rank: int
    
    # Core listing data
    listing: NormalizedListing
    
    # Enrichment data
    enrichment: EnrichedListing
    
    # Market context
    market_stats: Optional[MarketStats] = None
    
    # Scoring
    scores: ScoringBreakdown
    
    # Quick access fields for UI
    @property
    def is_good_deal(self) -> bool:
        """Check if this is considered a good deal."""
        return self.scores.value_score.deal_delta_percent > 10
    
    @property
    def has_high_risk(self) -> bool:
        """Check if this listing has high risk."""
        return self.scores.risk_score.score < 50
    
    @property
    def missing_critical_info(self) -> bool:
        """Check if critical info is missing."""
        return len(self.enrichment.missing_fields) > 0
