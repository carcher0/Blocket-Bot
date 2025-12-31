"""
Pydantic schemas for all evaluation engine data contracts.
Defines strict JSON schemas for LLM interactions and pipeline data flow.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


# === Enums ===

class Condition(str, Enum):
    """Normalized condition values."""
    NEW = "ny"
    LIKE_NEW = "som_ny"
    GOOD = "bra"
    OK = "ok"
    DEFECT = "defekt"
    UNKNOWN = "unknown"


class ProductFamily(str, Enum):
    """Supported product families for attribute packs."""
    PHONE = "phone"
    LAPTOP = "laptop"
    TABLET = "tablet"
    CAMERA = "camera"
    UNKNOWN = "unknown"


class RiskFlag(str, Enum):
    """Risk indicator flags."""
    UNUSUALLY_LOW_PRICE = "unusually_low_price"
    URGENCY_DETECTED = "urgency_detected"
    LOW_INFORMATION = "low_information"
    CONFLICTING_ATTRIBUTES = "conflicting_attributes"
    SUSPICIOUS_PAYMENT = "suspicious_payment"
    NO_IMAGES = "no_images"
    NEW_SELLER = "new_seller"


# === Query Analysis ===

class ClusterInfo(BaseModel):
    """Information about a price/title cluster."""
    label: str
    median_price: Optional[float] = None
    count: int
    example_titles: list[str] = Field(default_factory=list, max_length=5)


class QueryAnalysisResult(BaseModel):
    """Result from query analysis step."""
    query: str
    product_family: ProductFamily = ProductFamily.UNKNOWN
    confidence: float = Field(ge=0, le=1)
    key_attributes: list[str] = Field(default_factory=list)
    clusters: list[ClusterInfo] = Field(default_factory=list)
    is_ambiguous: bool = False
    clarifying_question: Optional[str] = None
    clarifying_options: list[str] = Field(default_factory=list)
    probe_sample_size: int = 0


# === Attribute Extraction ===

class ExtractedAttribute(BaseModel):
    """Single extracted attribute with confidence and evidence."""
    name: str
    value: Any
    confidence: float = Field(ge=0, le=1)
    evidence_span: Optional[str] = None  # Text snippet that supports extraction
    source: str = "regex"  # "regex" or "llm"


class ExtractedAttributes(BaseModel):
    """All extracted attributes for a listing."""
    listing_id: str
    product_family: ProductFamily = ProductFamily.UNKNOWN
    
    # Common attributes
    storage_gb: Optional[int] = None
    condition: Condition = Condition.UNKNOWN
    has_cracks: Optional[bool] = None
    battery_health: Optional[int] = Field(default=None, ge=0, le=100)
    has_warranty: Optional[bool] = None
    has_receipt: Optional[bool] = None
    is_locked: Optional[bool] = None  # Carrier locked
    color: Optional[str] = None
    model_variant: Optional[str] = None  # e.g., "iPhone 15 Pro Max"
    year: Optional[int] = None
    
    # Extraction metadata
    attributes: list[ExtractedAttribute] = Field(default_factory=list)
    extraction_confidence: float = Field(default=0.5, ge=0, le=1)
    llm_fallback_used: bool = False


# === Canonicalization ===

class CanonicalKey(BaseModel):
    """Canonical key for grouping comparable items."""
    family: ProductFamily
    model_variant: Optional[str] = None
    storage_bucket: Optional[str] = None  # "64GB", "128GB", etc.
    condition_bucket: Optional[str] = None  # "new", "good", "fair"
    
    def to_tuple(self) -> tuple:
        return (self.family, self.model_variant, self.storage_bucket, self.condition_bucket)


# === Comps (Comparable Groups) ===

class CompsStats(BaseModel):
    """Statistics for a comparison group."""
    median_price: float
    iqr: float  # Interquartile range
    q1: float  # 25th percentile
    q3: float  # 75th percentile
    min_price: float
    max_price: float
    n: int  # Sample size
    time_window_days: Optional[int] = None


class CompsGroup(BaseModel):
    """A group of comparable listings."""
    comps_key: CanonicalKey
    listing_ids: list[str] = Field(default_factory=list)
    stats: Optional[CompsStats] = None
    relaxation_level: int = 0  # 0 = exact match, higher = more relaxed
    is_sufficient: bool = True  # Has min sample size


# === Scoring ===

class ValueScore(BaseModel):
    """Score based on price vs market."""
    score: float = Field(ge=0, le=100)
    asking_price: Optional[float] = None
    expected_price: Optional[float] = None  # Median of comps
    deal_delta: Optional[float] = None  # (expected - asking) / expected
    comps_key: Optional[str] = None
    comps_n: int = 0


class PreferenceMatchScore(BaseModel):
    """Score based on preference matching."""
    score: float = Field(ge=0, le=100)
    hard_filters_passed: bool = True
    soft_scores: dict[str, float] = Field(default_factory=dict)  # preference -> score
    missing_info_penalties: list[str] = Field(default_factory=list)
    failed_hard_filters: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    """Risk assessment for a listing."""
    score: float = Field(ge=0, le=100)  # 0 = no risk, 100 = high risk
    flags: list[RiskFlag] = Field(default_factory=list)
    explanations: dict[str, str] = Field(default_factory=dict)  # flag -> reason


class ListingScores(BaseModel):
    """All scores for a single listing."""
    listing_id: str
    value_score: ValueScore
    preference_score: PreferenceMatchScore
    risk_assessment: RiskAssessment
    final_score: float = Field(ge=0, le=100)
    
    # Weights used
    value_weight: float = 0.5
    preference_weight: float = 0.35
    risk_weight: float = 0.15


# === Ranked Results ===

class RankedListing(BaseModel):
    """A listing with all evaluation data."""
    listing_id: str
    url: str
    title: Optional[str] = None
    asking_price: Optional[float] = None
    location: Optional[str] = None
    
    # Extracted data
    attributes: ExtractedAttributes
    canonical_key: Optional[CanonicalKey] = None
    
    # Scores
    scores: ListingScores
    
    # Explanation
    summary: Optional[str] = None  # LLM-generated summary
    checklist: list[str] = Field(default_factory=list)  # "Ask seller about..."
    
    # Ranking
    rank: int = 0


class ClarifyingQuestion(BaseModel):
    """A question to ask the user for better recommendations."""
    question: str
    options: list[str] = Field(default_factory=list)
    reason: str  # Why this question helps
    information_gain: float = Field(default=0.5, ge=0, le=1)


# === Final Evaluation Result ===

class EvaluationResult(BaseModel):
    """Complete result from the evaluation pipeline."""
    # Input reference
    query: str
    watch_id: Optional[str] = None
    evaluated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    # Analysis
    query_analysis: QueryAnalysisResult
    
    # Results
    ranked_listings: list[RankedListing] = Field(default_factory=list)
    total_evaluated: int = 0
    filtered_out: int = 0  # Failed hard filters
    
    # Market context
    comps_groups: list[CompsGroup] = Field(default_factory=list)
    
    # User interaction
    questions: list[ClarifyingQuestion] = Field(default_factory=list)
    
    # Quality flags
    data_quality_notes: list[str] = Field(default_factory=list)


# === LLM Interaction Schemas ===

class LLMClassificationRequest(BaseModel):
    """Request to LLM for classification."""
    query: str
    sample_titles: list[str]
    sample_prices: list[Optional[float]]
    cluster_descriptions: list[str] = Field(default_factory=list)


class LLMClassificationResponse(BaseModel):
    """Response from LLM classification."""
    product_family: str
    confidence: float = Field(ge=0, le=1)
    key_attributes: list[str]
    evidence: list[str]  # Examples from titles
    clarifying_questions: list[str] = Field(default_factory=list)


class LLMExtractionRequest(BaseModel):
    """Request to LLM for attribute extraction."""
    title: str
    description: Optional[str] = None
    attribute_schema: dict[str, str]  # attribute_name -> description


class LLMExtractionResponse(BaseModel):
    """Response from LLM extraction."""
    attributes: list[ExtractedAttribute]
    confidence: float = Field(ge=0, le=1)


class LLMExplanationRequest(BaseModel):
    """Request to LLM for generating explanations."""
    listings: list[dict]  # Simplified listing data
    preferences: dict
    comps_summary: dict


class LLMExplanationResponse(BaseModel):
    """Response from LLM explanation."""
    explanations: list[dict]  # {listing_id, summary, check_list}
    questions: list[ClarifyingQuestion]
