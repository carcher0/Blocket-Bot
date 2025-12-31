"""
Base class for attribute extraction packs.
Each pack defines attributes, extraction rules, and normalization for a product family.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional
import re

from ..schemas import (
    ExtractedAttribute,
    ExtractedAttributes,
    ProductFamily,
    Condition,
    CanonicalKey,
)


class AttributePack(ABC):
    """Base class for product-specific attribute extraction."""

    # Override in subclasses
    FAMILY: ProductFamily = ProductFamily.UNKNOWN
    
    # Attributes that are critical for comparison
    KEY_ATTRIBUTES: list[str] = []
    
    # Comps key dimensions (in order of importance for relaxation)
    COMPS_DIMENSIONS: list[str] = []

    # Condition mapping
    CONDITION_PATTERNS: dict[str, Condition] = {
        r"\bny\b": Condition.NEW,
        r"\bsom\s*ny\b": Condition.LIKE_NEW,
        r"\bnyskick\b": Condition.LIKE_NEW,
        r"\bfelfri\b": Condition.LIKE_NEW,
        r"\bbra\s*skick\b": Condition.GOOD,
        r"\bgott\s*skick\b": Condition.GOOD,
        r"\bok\s*skick\b": Condition.OK,
        r"\banvänd\b": Condition.OK,
        r"\bdefekt\b": Condition.DEFECT,
        r"\btrasig\b": Condition.DEFECT,
        r"\bsönder\b": Condition.DEFECT,
    }

    def extract(self, listing: dict) -> ExtractedAttributes:
        """
        Extract attributes from a listing.
        
        Args:
            listing: Normalized listing dict with title, raw, etc.
            
        Returns:
            ExtractedAttributes with all found attributes
        """
        listing_id = str(listing.get("listing_id", ""))
        title = listing.get("title", "") or ""
        raw = listing.get("raw", {}) or {}
        description = raw.get("body", "") or raw.get("description", "") or ""
        
        # Combine title and description for extraction
        text = f"{title} {description}".lower()
        
        # Extract all attributes
        attributes = self._extract_attributes(text, title, raw)
        
        # Build result
        result = ExtractedAttributes(
            listing_id=listing_id,
            product_family=self.FAMILY,
            attributes=attributes,
        )
        
        # Map common attributes to typed fields
        for attr in attributes:
            if attr.name == "storage_gb" and attr.value is not None:
                result.storage_gb = int(attr.value)
            elif attr.name == "condition" and attr.value is not None:
                result.condition = attr.value
            elif attr.name == "has_cracks":
                result.has_cracks = attr.value
            elif attr.name == "battery_health" and attr.value is not None:
                result.battery_health = int(attr.value)
            elif attr.name == "has_warranty":
                result.has_warranty = attr.value
            elif attr.name == "has_receipt":
                result.has_receipt = attr.value
            elif attr.name == "is_locked":
                result.is_locked = attr.value
            elif attr.name == "color":
                result.color = attr.value
            elif attr.name == "model_variant":
                result.model_variant = attr.value
        
        # Compute overall confidence
        key_found = sum(1 for a in attributes if a.name in self.KEY_ATTRIBUTES and a.value is not None)
        result.extraction_confidence = key_found / len(self.KEY_ATTRIBUTES) if self.KEY_ATTRIBUTES else 0.5
        
        return result

    @abstractmethod
    def _extract_attributes(self, text: str, title: str, raw: dict) -> list[ExtractedAttribute]:
        """
        Extract product-specific attributes.
        
        Args:
            text: Lowercased combined title + description
            title: Original title
            raw: Raw API response
            
        Returns:
            List of extracted attributes
        """
        pass

    def extract_condition(self, text: str) -> tuple[Condition, float, Optional[str]]:
        """
        Extract condition from text.
        
        Returns:
            (condition, confidence, evidence_span)
        """
        for pattern, condition in self.CONDITION_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return condition, 0.8, match.group(0)
        return Condition.UNKNOWN, 0.3, None

    def create_canonical_key(self, attrs: ExtractedAttributes) -> CanonicalKey:
        """Create a canonical key for grouping."""
        # Storage bucket
        storage_bucket = None
        if attrs.storage_gb:
            if attrs.storage_gb <= 64:
                storage_bucket = "64GB"
            elif attrs.storage_gb <= 128:
                storage_bucket = "128GB"
            elif attrs.storage_gb <= 256:
                storage_bucket = "256GB"
            elif attrs.storage_gb <= 512:
                storage_bucket = "512GB"
            else:
                storage_bucket = "1TB+"
        
        # Condition bucket
        condition_bucket = None
        if attrs.condition != Condition.UNKNOWN:
            if attrs.condition in (Condition.NEW, Condition.LIKE_NEW):
                condition_bucket = "new"
            elif attrs.condition == Condition.GOOD:
                condition_bucket = "good"
            else:
                condition_bucket = "fair"
        
        return CanonicalKey(
            family=self.FAMILY,
            model_variant=attrs.model_variant,
            storage_bucket=storage_bucket,
            condition_bucket=condition_bucket,
        )

    def get_missing_key_attributes(self, attrs: ExtractedAttributes) -> list[str]:
        """Get list of key attributes that are missing."""
        missing = []
        for attr_name in self.KEY_ATTRIBUTES:
            value = getattr(attrs, attr_name, None)
            if value is None:
                missing.append(attr_name)
        return missing
