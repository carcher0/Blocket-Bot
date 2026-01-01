"""
Risk detection module: Identify potential red flags in listings.
"""
import re
from typing import Optional

from .schemas import RiskFlag, RiskAssessment, CompsStats


# Urgency language patterns (Swedish + English)
URGENCY_PATTERNS = [
    r"\bsnabb\s*(affär|försäljning)\b",
    r"\bsäljes\s*snabb(t|are)?\b",
    r"\bmåste\s*(bort|säljas)\b",
    r"\bidag\b.*\b(sälj|pris)\b",
    r"\bakut\b",
    r"\bquick\s*sale\b",
    r"\bmust\s*(go|sell)\b",
    r"\benda\s*dag\b",
    r"\bsista\s*chans\b",
]

# Suspicious payment patterns
SUSPICIOUS_PAYMENT_PATTERNS = [
    r"\bswish\s*först\b",
    r"\bförskott\b",
    r"\bförskottsbetalning\b",
    r"\bcrypto\b",
    r"\bbitcoin\b",
    r"\bbetala\s*innan\b",
    r"\bpay\s*before\b",
    r"\bwestern\s*union\b",
]

# Minimum description length for "low information" flag
MIN_DESCRIPTION_LENGTH = 50


def assess_risk(
    listing: dict,
    comps_stats: Optional[CompsStats] = None,
    extracted_text: str = "",
) -> RiskAssessment:
    """
    Assess risk level for a listing.
    
    Args:
        listing: Normalized listing dict
        comps_stats: Stats from comparison group (for price analysis)
        extracted_text: Combined title + description for pattern matching
        
    Returns:
        RiskAssessment with score and flags
    """
    flags: list[RiskFlag] = []
    explanations: dict[str, str] = {}
    
    # Get price
    price_data = listing.get("price", {})
    if isinstance(price_data, dict):
        price = price_data.get("amount")
    else:
        price = None
    
    # Get text for analysis
    title = listing.get("title", "") or ""
    raw = listing.get("raw", {}) or {}
    description = raw.get("body", "") or raw.get("description", "") or ""
    text = f"{title} {description}".lower() if not extracted_text else extracted_text.lower()
    
    # === Price-based risks ===
    if price and comps_stats:
        if price < comps_stats.q1 - 1.5 * comps_stats.iqr:
            flags.append(RiskFlag.UNUSUALLY_LOW_PRICE)
            diff = comps_stats.median_price - price
            pct = (diff / comps_stats.median_price * 100) if comps_stats.median_price else 0
            explanations["unusually_low_price"] = (
                f"Pris {price:,.0f} kr är {pct:.0f}% under marknadspris ({comps_stats.median_price:,.0f} kr)"
            )
    
    # === Urgency language ===
    for pattern in URGENCY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            flags.append(RiskFlag.URGENCY_DETECTED)
            explanations["urgency_detected"] = f"Stressat språk upptäckt: '{match.group(0)}'"
            break
    
    # === Suspicious payment ===
    for pattern in SUSPICIOUS_PAYMENT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            flags.append(RiskFlag.SUSPICIOUS_PAYMENT)
            explanations["suspicious_payment"] = f"Misstänkt betalningskrav: '{match.group(0)}'"
            break
    
    # === Low information ===
    total_text_length = len(title) + len(description)
    if total_text_length < MIN_DESCRIPTION_LENGTH:
        flags.append(RiskFlag.LOW_INFORMATION)
        explanations["low_information"] = (
            f"Kort beskrivning ({total_text_length} tecken). Svårt att bedöma skick."
        )
    
    # === No images ===
    images = raw.get("images", []) or raw.get("image_urls", []) or []
    if not images:
        flags.append(RiskFlag.NO_IMAGES)
        explanations["no_images"] = "Inga bilder i annonsen"
    
    # === Compute overall score ===
    # Base score starts at 0 (no risk), increases with each flag
    risk_weights = {
        RiskFlag.UNUSUALLY_LOW_PRICE: 35,
        RiskFlag.URGENCY_DETECTED: 20,
        RiskFlag.SUSPICIOUS_PAYMENT: 40,
        RiskFlag.LOW_INFORMATION: 15,
        RiskFlag.NO_IMAGES: 20,
        RiskFlag.CONFLICTING_ATTRIBUTES: 25,
        RiskFlag.NEW_SELLER: 10,
    }
    
    score = sum(risk_weights.get(flag, 10) for flag in flags)
    score = min(score, 100)  # Cap at 100
    
    return RiskAssessment(
        score=score,
        flags=list(set(flags)),  # Dedupe
        explanations=explanations,
    )


def has_high_risk(assessment: RiskAssessment, threshold: float = 50) -> bool:
    """Check if risk level is above threshold."""
    return assessment.score >= threshold


def get_risk_summary(assessment: RiskAssessment) -> str:
    """Get human-readable risk summary."""
    if not assessment.flags:
        return "✅ Inga uppenbara riskindikatorer"
    
    if assessment.score >= 50:
        level = "⚠️ Hög risk"
    elif assessment.score >= 25:
        level = "⚡ Måttlig risk"
    else:
        level = "ℹ️ Låg risk"
    
    summaries = list(assessment.explanations.values())
    return f"{level}: {'; '.join(summaries[:2])}"
