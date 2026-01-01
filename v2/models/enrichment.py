"""
Enrichment models - extracted attributes and risk analysis.
"""
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExtractedAttribute(BaseModel):
    """A single extracted attribute with confidence."""
    name: str
    value: Any
    confidence: float = Field(ge=0, le=1, description="Extraction confidence")
    evidence_span: Optional[str] = Field(
        default=None,
        description="The text span that was used to extract this value"
    )
    source: str = Field(
        default="regex",
        description="Extraction method: 'regex', 'llm', 'structured'"
    )


class RiskFlag(BaseModel):
    """A detected risk indicator."""
    flag_type: str = Field(description="Type of risk: 'price', 'seller', 'content', 'missing'")
    severity: float = Field(ge=0, le=1, description="How severe this risk is")
    explanation: str = Field(description="Human-readable explanation")
    evidence: Optional[str] = Field(default=None, description="Supporting evidence")


class SellerQuestion(BaseModel):
    """A question to ask the seller."""
    question: str = Field(description="The question text, ready to copy-paste")
    reason: str = Field(description="Why this question is important")
    relates_to: str = Field(description="Which missing info or risk this addresses")


class EnrichedListing(BaseModel):
    """
    A listing enriched with extracted attributes, risks, and seller questions.
    """
    listing_id: str
    
    # Extracted attributes
    extracted_attributes: dict[str, ExtractedAttribute] = Field(
        default_factory=dict,
        description="Attribute name -> extracted value with confidence"
    )
    
    # Overall extraction confidence
    extraction_confidence: float = Field(
        default=0.5,
        ge=0, le=1,
        description="Overall confidence in extracted attributes"
    )
    
    # Missing fields that should have been found
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Critical attributes that couldn't be extracted"
    )
    
    # Seller questions for missing/unclear info
    seller_questions: list[SellerQuestion] = Field(
        default_factory=list,
        description="Generated questions to ask the seller"
    )
    
    # Risk analysis
    risk_flags: list[RiskFlag] = Field(
        default_factory=list,
        description="Detected risk indicators"
    )
    
    # Did we need LLM fallback?
    llm_fallback_used: bool = Field(
        default=False,
        description="Whether LLM was used for extraction"
    )

    def get_attribute_value(self, name: str, default: Any = None) -> Any:
        """Get an extracted attribute value by name."""
        attr = self.extracted_attributes.get(name)
        if attr is not None:
            return attr.value
        return default
    
    def get_attribute_confidence(self, name: str) -> float:
        """Get confidence for a specific attribute."""
        attr = self.extracted_attributes.get(name)
        if attr is not None:
            return attr.confidence
        return 0.0
    
    @property
    def total_risk_score(self) -> float:
        """Calculate total risk score from flags."""
        if not self.risk_flags:
            return 0.0
        return sum(f.severity for f in self.risk_flags) / len(self.risk_flags)
