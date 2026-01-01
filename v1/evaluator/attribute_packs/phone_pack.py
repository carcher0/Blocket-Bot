"""
PhonePack: Attribute extraction for mobile phones.
Optimized for iPhone and other smartphones on Blocket.
"""
import re
from typing import Optional

from .base import AttributePack
from ..schemas import (
    ExtractedAttribute,
    ProductFamily,
    Condition,
)


class PhonePack(AttributePack):
    """Attribute extraction pack for mobile phones."""

    FAMILY = ProductFamily.PHONE
    
    KEY_ATTRIBUTES = [
        "model_variant",
        "storage_gb",
        "condition",
        "battery_health",
        "has_cracks",
    ]
    
    COMPS_DIMENSIONS = [
        "model_variant",
        "storage_bucket",
        "condition_bucket",
    ]

    # iPhone model patterns
    IPHONE_PATTERNS = [
        # iPhone 15 series
        (r"iphone\s*15\s*pro\s*max", "iPhone 15 Pro Max"),
        (r"iphone\s*15\s*pro", "iPhone 15 Pro"),
        (r"iphone\s*15\s*plus", "iPhone 15 Plus"),
        (r"iphone\s*15", "iPhone 15"),
        # iPhone 14 series
        (r"iphone\s*14\s*pro\s*max", "iPhone 14 Pro Max"),
        (r"iphone\s*14\s*pro", "iPhone 14 Pro"),
        (r"iphone\s*14\s*plus", "iPhone 14 Plus"),
        (r"iphone\s*14", "iPhone 14"),
        # iPhone 13 series
        (r"iphone\s*13\s*pro\s*max", "iPhone 13 Pro Max"),
        (r"iphone\s*13\s*pro", "iPhone 13 Pro"),
        (r"iphone\s*13\s*mini", "iPhone 13 Mini"),
        (r"iphone\s*13", "iPhone 13"),
        # iPhone 12 series
        (r"iphone\s*12\s*pro\s*max", "iPhone 12 Pro Max"),
        (r"iphone\s*12\s*pro", "iPhone 12 Pro"),
        (r"iphone\s*12\s*mini", "iPhone 12 Mini"),
        (r"iphone\s*12", "iPhone 12"),
        # iPhone 11 series
        (r"iphone\s*11\s*pro\s*max", "iPhone 11 Pro Max"),
        (r"iphone\s*11\s*pro", "iPhone 11 Pro"),
        (r"iphone\s*11", "iPhone 11"),
        # iPhone SE
        (r"iphone\s*se\s*3", "iPhone SE 3"),
        (r"iphone\s*se\s*2", "iPhone SE 2"),
        (r"iphone\s*se\s*\(?2022\)?", "iPhone SE 3"),
        (r"iphone\s*se\s*\(?2020\)?", "iPhone SE 2"),
        (r"iphone\s*se", "iPhone SE"),
        # Older models
        (r"iphone\s*x[rs]", "iPhone XR/XS"),
        (r"iphone\s*x", "iPhone X"),
        (r"iphone\s*8\s*plus", "iPhone 8 Plus"),
        (r"iphone\s*8", "iPhone 8"),
    ]

    # Samsung patterns
    SAMSUNG_PATTERNS = [
        (r"samsung\s*galaxy\s*s24\s*ultra", "Samsung Galaxy S24 Ultra"),
        (r"samsung\s*galaxy\s*s24\s*\+|plus", "Samsung Galaxy S24+"),
        (r"samsung\s*galaxy\s*s24", "Samsung Galaxy S24"),
        (r"samsung\s*galaxy\s*s23\s*ultra", "Samsung Galaxy S23 Ultra"),
        (r"samsung\s*galaxy\s*s23", "Samsung Galaxy S23"),
        (r"samsung\s*galaxy\s*s22", "Samsung Galaxy S22"),
        (r"samsung\s*galaxy\s*s21", "Samsung Galaxy S21"),
        (r"galaxy\s*s24", "Samsung Galaxy S24"),
        (r"galaxy\s*s23", "Samsung Galaxy S23"),
    ]

    # Storage patterns
    STORAGE_PATTERNS = [
        (r"(\d+)\s*gb", "gb"),
        (r"(\d+)\s*tb", "tb"),
    ]

    # Color patterns (Swedish + English)
    COLOR_PATTERNS = {
        r"\b(svart|black)\b": "svart",
        r"\b(vit|white)\b": "vit",
        r"\b(blå|blue)\b": "blå",
        r"\b(guld|gold)\b": "guld",
        r"\b(silver)\b": "silver",
        r"\b(rosa|pink)\b": "rosa",
        r"\b(röd|red)\b": "röd",
        r"\b(grön|green)\b": "grön",
        r"\b(lila|purple)\b": "lila",
        r"\b(grå|gr[åa]tt|gray|grey)\b": "grå",
        r"\b(natural\s*titanium)\b": "natural titanium",
        r"\b(blue\s*titanium)\b": "blue titanium",
        r"\b(white\s*titanium)\b": "white titanium",
        r"\b(black\s*titanium)\b": "black titanium",
    }

    # Crack/damage patterns
    CRACK_PATTERNS = [
        r"sprick",
        r"crack",
        r"sprucken",
        r"spräck",
        r"skärm.*skada",
        r"skada.*skärm",
        r"glas.*trasig",
        r"trasig.*glas",
    ]

    # No crack patterns (negation)
    NO_CRACK_PATTERNS = [
        r"inga?\s*sprick",
        r"utan\s*sprick",
        r"ej\s*sprick",
        r"inte\s*sprick",
        r"no\s*crack",
        r"felfri",
        r"perfekt\s*skärm",
        r"fint\s*glas",
    ]

    # Battery patterns
    BATTERY_PATTERNS = [
        r"batteri.*?(\d{1,3})\s*%",
        r"battery.*?(\d{1,3})\s*%",
        r"(\d{1,3})\s*%\s*batteri",
        r"batterihälsa\s*(\d{1,3})",
        r"battery\s*health\s*(\d{1,3})",
    ]

    # Warranty/receipt patterns
    WARRANTY_PATTERNS = [
        r"\bgaranti\b",
        r"\bwarranty\b",
        r"\bapple\s*care\b",
        r"\bapplecare\b",
    ]
    
    RECEIPT_PATTERNS = [
        r"\bkvitto\b",
        r"\breceipt\b",
        r"\bfaktura\b",
        r"\bköpehandling\b",
    ]

    # Locked/unlocked patterns
    LOCKED_PATTERNS = [
        r"\blåst\b",
        r"\boperatörslåst\b",
        r"\blocked\b",
    ]
    
    UNLOCKED_PATTERNS = [
        r"\bolåst\b",
        r"\bunlocked\b",
        r"\bfabrikslåst\b",  # Factory unlocked
        r"\bfri\s*från\s*operatör\b",
    ]

    def _extract_attributes(self, text: str, title: str, raw: dict) -> list[ExtractedAttribute]:
        """Extract phone-specific attributes."""
        attributes = []

        # Model variant
        model = self._extract_model(text)
        if model:
            attributes.append(ExtractedAttribute(
                name="model_variant",
                value=model[0],
                confidence=model[1],
                evidence_span=model[2],
                source="regex",
            ))

        # Storage
        storage = self._extract_storage(text)
        if storage:
            attributes.append(ExtractedAttribute(
                name="storage_gb",
                value=storage[0],
                confidence=storage[1],
                evidence_span=storage[2],
                source="regex",
            ))

        # Condition
        condition, conf, evidence = self.extract_condition(text)
        attributes.append(ExtractedAttribute(
            name="condition",
            value=condition,
            confidence=conf,
            evidence_span=evidence,
            source="regex",
        ))

        # Cracks
        has_cracks = self._extract_cracks(text)
        if has_cracks is not None:
            attributes.append(ExtractedAttribute(
                name="has_cracks",
                value=has_cracks[0],
                confidence=has_cracks[1],
                evidence_span=has_cracks[2],
                source="regex",
            ))

        # Battery health
        battery = self._extract_battery(text)
        if battery:
            attributes.append(ExtractedAttribute(
                name="battery_health",
                value=battery[0],
                confidence=battery[1],
                evidence_span=battery[2],
                source="regex",
            ))

        # Color
        color = self._extract_color(text)
        if color:
            attributes.append(ExtractedAttribute(
                name="color",
                value=color[0],
                confidence=color[1],
                evidence_span=color[2],
                source="regex",
            ))

        # Warranty
        warranty = self._extract_warranty(text)
        if warranty is not None:
            attributes.append(ExtractedAttribute(
                name="has_warranty",
                value=warranty[0],
                confidence=warranty[1],
                evidence_span=warranty[2],
                source="regex",
            ))

        # Receipt
        receipt = self._extract_receipt(text)
        if receipt is not None:
            attributes.append(ExtractedAttribute(
                name="has_receipt",
                value=receipt[0],
                confidence=receipt[1],
                evidence_span=receipt[2],
                source="regex",
            ))

        # Locked status
        locked = self._extract_locked(text)
        if locked is not None:
            attributes.append(ExtractedAttribute(
                name="is_locked",
                value=locked[0],
                confidence=locked[1],
                evidence_span=locked[2],
                source="regex",
            ))

        return attributes

    def _extract_model(self, text: str) -> Optional[tuple[str, float, str]]:
        """Extract phone model."""
        # Try iPhone patterns first
        for pattern, model_name in self.IPHONE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (model_name, 0.95, match.group(0))
        
        # Try Samsung patterns
        for pattern, model_name in self.SAMSUNG_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (model_name, 0.9, match.group(0))
        
        return None

    def _extract_storage(self, text: str) -> Optional[tuple[int, float, str]]:
        """Extract storage size in GB."""
        for pattern, unit in self.STORAGE_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                if unit == "tb":
                    value *= 1024
                # Validate reasonable storage sizes
                if value in [32, 64, 128, 256, 512, 1024, 2048]:
                    return (value, 0.95, match.group(0))
                elif value < 2048:
                    return (value, 0.7, match.group(0))
        return None

    def _extract_cracks(self, text: str) -> Optional[tuple[bool, float, str]]:
        """Extract crack status."""
        # Check for explicit no-crack statements first
        for pattern in self.NO_CRACK_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (False, 0.9, match.group(0))
        
        # Check for crack mentions
        for pattern in self.CRACK_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (True, 0.85, match.group(0))
        
        return None

    def _extract_battery(self, text: str) -> Optional[tuple[int, float, str]]:
        """Extract battery health percentage."""
        for pattern in self.BATTERY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = int(match.group(1))
                if 0 <= value <= 100:
                    return (value, 0.95, match.group(0))
        return None

    def _extract_color(self, text: str) -> Optional[tuple[str, float, str]]:
        """Extract phone color."""
        for pattern, color in self.COLOR_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (color, 0.85, match.group(0))
        return None

    def _extract_warranty(self, text: str) -> Optional[tuple[bool, float, str]]:
        """Extract warranty status."""
        for pattern in self.WARRANTY_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (True, 0.8, match.group(0))
        return None

    def _extract_receipt(self, text: str) -> Optional[tuple[bool, float, str]]:
        """Extract receipt status."""
        for pattern in self.RECEIPT_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (True, 0.8, match.group(0))
        return None

    def _extract_locked(self, text: str) -> Optional[tuple[bool, float, str]]:
        """Extract carrier lock status."""
        # Check unlocked first
        for pattern in self.UNLOCKED_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (False, 0.85, match.group(0))
        
        # Check locked
        for pattern in self.LOCKED_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (True, 0.8, match.group(0))
        
        return None
