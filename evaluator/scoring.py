"""
Scoring module: Combine Value, Preference, and Risk into final ranking.
"""
from typing import Optional

from .schemas import (
    ValueScore,
    PreferenceMatchScore,
    RiskAssessment,
    ListingScores,
    CompsGroup,
    ExtractedAttributes,
    Condition,
)
from .valuation import compute_deal_delta, compute_expected_price
from .risk import assess_risk


def compute_value_score(
    asking_price: Optional[float],
    comps: Optional[CompsGroup],
) -> ValueScore:
    """
    Compute value score based on price vs market.
    
    Score 0-100 where:
    - 50 = at market price (median)
    - 100 = significantly below market
    - 0 = significantly above market
    """
    if not asking_price or not comps or not comps.stats:
        return ValueScore(
            score=50,  # Neutral if we can't compare
            asking_price=asking_price,
            comps_n=comps.stats.n if comps and comps.stats else 0,
        )
    
    expected = compute_expected_price(comps)
    if not expected or expected <= 0:
        return ValueScore(score=50, asking_price=asking_price, comps_n=0)
    
    deal_delta = compute_deal_delta(asking_price, expected)
    
    # Convert deal_delta to 0-100 score
    # deal_delta of 0.3 (30% below market) -> score ~80
    # deal_delta of -0.3 (30% above market) -> score ~20
    # deal_delta of 0 -> score 50
    raw_score = 50 + deal_delta * 100
    score = max(0, min(100, raw_score))
    
    return ValueScore(
        score=score,
        asking_price=asking_price,
        expected_price=expected,
        deal_delta=deal_delta,
        comps_key=str(comps.comps_key.to_tuple()) if comps.comps_key else None,
        comps_n=comps.stats.n if comps.stats else 0,
    )


def compute_preference_score(
    attrs: ExtractedAttributes,
    preferences: dict,
) -> PreferenceMatchScore:
    """
    Compute how well a listing matches user preferences.
    
    Preferences dict example:
    {
        "condition": "bra",          # Minimum condition
        "no_cracks": True,           # Hard filter
        "min_battery_health": 80,    # Soft preference
        "max_price": 8000,           # Hard filter
        "shipping_required": False,  # Soft preference
    }
    """
    hard_filters_passed = True
    failed_hard_filters: list[str] = []
    soft_scores: dict[str, float] = {}
    missing_penalties: list[str] = []
    
    # === Hard filters ===
    
    # no_cracks: hard filter if set to True
    if preferences.get("no_cracks") is True:
        if attrs.has_cracks is True:
            hard_filters_passed = False
            failed_hard_filters.append("Har sprickor (krav: inga sprickor)")
        elif attrs.has_cracks is None:
            missing_penalties.append("Sprickstatus okänd")
    
    # Condition: minimum required
    min_condition = preferences.get("condition")
    if min_condition:
        condition_order = [
            Condition.NEW, Condition.LIKE_NEW, Condition.GOOD, 
            Condition.OK, Condition.DEFECT, Condition.UNKNOWN
        ]
        try:
            min_idx = condition_order.index(Condition(min_condition))
            actual_idx = condition_order.index(attrs.condition)
            
            if attrs.condition == Condition.UNKNOWN:
                missing_penalties.append("Skick ej angivet")
            elif actual_idx > min_idx:  # Worse condition
                hard_filters_passed = False
                failed_hard_filters.append(f"Skick ({attrs.condition.value}) under minimum ({min_condition})")
        except ValueError:
            pass
    
    # === Soft preferences ===
    
    # Battery health
    min_battery = preferences.get("min_battery_health")
    if min_battery:
        if attrs.battery_health is not None:
            if attrs.battery_health >= min_battery:
                soft_scores["battery"] = 100
            else:
                # Partial score based on how close
                soft_scores["battery"] = max(0, (attrs.battery_health / min_battery) * 100)
        else:
            missing_penalties.append("Batterihälsa okänd")
            soft_scores["battery"] = 50  # Neutral
    
    # Warranty
    if preferences.get("has_warranty"):
        if attrs.has_warranty is True:
            soft_scores["warranty"] = 100
        elif attrs.has_warranty is False:
            soft_scores["warranty"] = 30
        else:
            soft_scores["warranty"] = 50
            missing_penalties.append("Garantistatus okänd")
    
    # Receipt
    if preferences.get("has_receipt"):
        if attrs.has_receipt is True:
            soft_scores["receipt"] = 100
        elif attrs.has_receipt is False:
            soft_scores["receipt"] = 40
        else:
            soft_scores["receipt"] = 50
    
    # Unlocked preference
    if preferences.get("unlocked"):
        if attrs.is_locked is False:
            soft_scores["unlocked"] = 100
        elif attrs.is_locked is True:
            soft_scores["unlocked"] = 20
        else:
            soft_scores["unlocked"] = 60
    
    # === Compute final score ===
    if not hard_filters_passed:
        score = 0
    else:
        # Average of soft scores, minus penalty for missing info
        if soft_scores:
            avg_soft = sum(soft_scores.values()) / len(soft_scores)
        else:
            avg_soft = 80  # Default if no soft prefs set
        
        # Penalty for missing info
        penalty = len(missing_penalties) * 5
        score = max(0, min(100, avg_soft - penalty))
    
    return PreferenceMatchScore(
        score=score,
        hard_filters_passed=hard_filters_passed,
        soft_scores=soft_scores,
        missing_info_penalties=missing_penalties,
        failed_hard_filters=failed_hard_filters,
    )


def compute_final_score(
    value: ValueScore,
    preference: PreferenceMatchScore,
    risk: RiskAssessment,
    value_weight: float = 0.5,
    preference_weight: float = 0.35,
    risk_weight: float = 0.15,
) -> float:
    """
    Compute weighted final score.
    
    final = value_weight * ValueScore + preference_weight * PreferenceScore - risk_weight * RiskScore
    """
    # If hard filter failed, score is 0
    if not preference.hard_filters_passed:
        return 0.0
    
    weighted = (
        value_weight * value.score +
        preference_weight * preference.score -
        risk_weight * risk.score
    )
    
    return max(0, min(100, weighted))


def score_listing(
    listing: dict,
    attrs: ExtractedAttributes,
    comps: Optional[CompsGroup],
    preferences: dict,
) -> ListingScores:
    """
    Compute all scores for a single listing.
    """
    # Get price
    price_data = listing.get("price", {})
    if isinstance(price_data, dict):
        asking_price = price_data.get("amount")
    else:
        asking_price = None
    
    # Compute individual scores
    value_score = compute_value_score(asking_price, comps)
    preference_score = compute_preference_score(attrs, preferences)
    
    risk_assessment = assess_risk(
        listing=listing,
        comps_stats=comps.stats if comps else None,
    )
    
    final = compute_final_score(
        value_score,
        preference_score,
        risk_assessment,
    )
    
    return ListingScores(
        listing_id=str(listing.get("listing_id", "")),
        value_score=value_score,
        preference_score=preference_score,
        risk_assessment=risk_assessment,
        final_score=final,
    )
