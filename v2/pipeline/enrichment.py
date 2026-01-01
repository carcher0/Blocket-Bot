"""
Listing enrichment - extract attributes, detect risks, generate seller questions.
"""
import re
import logging
from typing import Any, Optional

from ..models.listing import NormalizedListing
from ..models.enrichment import (
    EnrichedListing,
    ExtractedAttribute,
    RiskFlag,
    SellerQuestion,
)
from ..models.discovery import DomainDiscoveryOutput


logger = logging.getLogger(__name__)


# Common urgency words that may indicate risks
URGENCY_WORDS = [
    "snabb affär", "måste sälja", "måste bort", "idag", 
    "akut", "asap", "snarast", "först till kvarn",
    "quick sale", "must go", "urgent",
]

# Trust indicators (positive)
TRUST_INDICATORS = [
    "kvitto", "garanti", "originalförpackning", "olåst",
    "aldrig använd", "nyskick", "oanvänd",
]


class ListingEnricher:
    """
    Enriches listings with extracted attributes, risks, and seller questions.
    Uses regex patterns first, falls back to LLM when needed.
    """

    def __init__(self, llm_client: Optional[Any] = None):
        """
        Args:
            llm_client: Optional LLM client for fallback extraction
        """
        self.llm_client = llm_client
        
        # Common patterns
        self.patterns = {
            "storage_gb": [
                r"(\d+)\s*gb",
                r"(\d+)\s*GB",
            ],
            "battery_health": [
                r"batteri[:\s]*(\d+)\s*%",
                r"battery[:\s]*(\d+)\s*%",
                r"batterihälsa[:\s]*(\d+)",
            ],
            "condition": [
                r"\b(nyskick|som ny|bra skick|ok skick|defekt)\b",
                r"\b(ny|like new|good|ok|defect)\b",
            ],
            "year": [
                r"\b(20\d{2})\b",
            ],
            "model_variant": [
                r"(pro\s*max|pro|plus|mini|standard)",
            ],
        }

    def enrich(
        self,
        listing: NormalizedListing,
        schema: Optional[DomainDiscoveryOutput] = None,
    ) -> EnrichedListing:
        """
        Enrich a single listing with extracted attributes.

        Args:
            listing: The listing to enrich
            schema: Domain schema for targeted extraction

        Returns:
            EnrichedListing with all extracted data
        """
        text = f"{listing.title or ''} {listing.description or ''}".lower()

        # Extract attributes using patterns
        extracted = self._extract_with_patterns(text)

        # Detect missing critical fields
        missing = self._detect_missing_fields(extracted, schema)

        # Generate seller questions for missing info
        questions = self._generate_seller_questions(missing, listing)

        # Detect risk flags
        risks = self._detect_risks(listing, text, extracted)

        # Calculate overall confidence
        if extracted:
            avg_confidence = sum(a.confidence for a in extracted.values()) / len(extracted)
        else:
            avg_confidence = 0.3

        return EnrichedListing(
            listing_id=listing.listing_id,
            extracted_attributes=extracted,
            extraction_confidence=avg_confidence,
            missing_fields=missing,
            seller_questions=questions,
            risk_flags=risks,
            llm_fallback_used=False,
        )

    def _extract_with_patterns(
        self,
        text: str,
    ) -> dict[str, ExtractedAttribute]:
        """Extract attributes using regex patterns."""
        extracted = {}

        for attr_name, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1) if match.groups() else match.group(0)
                    
                    # Convert to appropriate type
                    if attr_name in ["storage_gb", "battery_health", "year"]:
                        try:
                            value = int(value)
                        except ValueError:
                            continue

                    extracted[attr_name] = ExtractedAttribute(
                        name=attr_name,
                        value=value,
                        confidence=0.9,  # High confidence for regex match
                        evidence_span=match.group(0),
                        source="regex",
                    )
                    break  # Use first match

        # Check for trust indicators
        for indicator in TRUST_INDICATORS:
            if indicator in text:
                if "trust_signals" not in extracted:
                    extracted["trust_signals"] = ExtractedAttribute(
                        name="trust_signals",
                        value=[],
                        confidence=0.8,
                        source="regex",
                    )
                extracted["trust_signals"].value.append(indicator)

        return extracted

    def _detect_missing_fields(
        self,
        extracted: dict[str, ExtractedAttribute],
        schema: Optional[DomainDiscoveryOutput],
    ) -> list[str]:
        """Detect critical missing fields."""
        missing = []

        # Always check for condition
        if "condition" not in extracted:
            missing.append("condition")

        # Check schema's critical fields
        if schema:
            for attr in schema.attribute_candidates:
                if attr.critical_if_missing and attr.name not in extracted:
                    missing.append(attr.name)

        return missing

    def _generate_seller_questions(
        self,
        missing_fields: list[str],
        listing: NormalizedListing,
    ) -> list[SellerQuestion]:
        """Generate questions to ask the seller about missing info."""
        questions = []

        question_templates = {
            "condition": SellerQuestion(
                question="Vilket skick är produkten i? Några repor eller skador?",
                reason="Skick påverkar värdet och livslängden",
                relates_to="condition",
            ),
            "battery_health": SellerQuestion(
                question="Vad är batterihälsan (i procent)?",
                reason="Batterihälsa påverkar användbarhet och värde",
                relates_to="battery_health",
            ),
            "storage_gb": SellerQuestion(
                question="Hur mycket lagringsutrymme har den?",
                reason="Lagring påverkar prisvärdering",
                relates_to="storage_gb",
            ),
            "model_variant": SellerQuestion(
                question="Vilken exakt modell är det?",
                reason="Modell påverkar funktioner och marknadsvärde",
                relates_to="model_variant",
            ),
            "has_receipt": SellerQuestion(
                question="Finns kvitto eller garantibevis kvar?",
                reason="Kvitto ger trygghet vid köp",
                relates_to="has_receipt",
            ),
        }

        for field in missing_fields:
            if field in question_templates:
                questions.append(question_templates[field])

        return questions

    def _detect_risks(
        self,
        listing: NormalizedListing,
        text: str,
        extracted: dict[str, ExtractedAttribute],
    ) -> list[RiskFlag]:
        """Detect potential risk indicators."""
        risks = []

        # Check for urgency words
        for word in URGENCY_WORDS:
            if word in text:
                risks.append(RiskFlag(
                    flag_type="content",
                    severity=0.6,
                    explanation=f"Brådskandeord upptäckt: '{word}'",
                    evidence=word,
                ))
                break

        # Check for no images
        if listing.image_count == 0:
            risks.append(RiskFlag(
                flag_type="missing",
                severity=0.7,
                explanation="Inga bilder i annonsen",
            ))

        # Check for very low information
        if not listing.description or len(listing.description) < 20:
            risks.append(RiskFlag(
                flag_type="missing",
                severity=0.5,
                explanation="Mycket kort eller ingen beskrivning",
            ))

        # Check for low battery (if extracted)
        battery = extracted.get("battery_health")
        if battery and isinstance(battery.value, int) and battery.value < 80:
            risks.append(RiskFlag(
                flag_type="content",
                severity=0.4,
                explanation=f"Låg batterihälsa: {battery.value}%",
                evidence=str(battery.value),
            ))

        return risks

    def enrich_batch(
        self,
        listings: list[NormalizedListing],
        schema: Optional[DomainDiscoveryOutput] = None,
    ) -> list[EnrichedListing]:
        """Enrich multiple listings."""
        logger.info(f"Enriching {len(listings)} listings")
        return [self.enrich(listing, schema) for listing in listings]
