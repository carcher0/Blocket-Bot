"""
Scoring engine - deterministic scoring with transparent breakdown.
"""
import logging
from typing import Optional

from ..models.listing import NormalizedListing
from ..models.enrichment import EnrichedListing
from ..models.preferences import PreferenceProfile
from ..models.scoring import (
    MarketStats,
    ValueScore,
    PreferenceScore,
    RiskScore,
    ScoringBreakdown,
    RankedListing,
)


logger = logging.getLogger(__name__)


class ScoringEngine:
    """
    Deterministic scoring engine with transparent breakdown.
    All scores are 0-100, higher is better.
    """

    def __init__(
        self,
        value_weight: float = 0.50,
        preference_weight: float = 0.35,
        risk_weight: float = 0.15,
    ):
        self.value_weight = value_weight
        self.preference_weight = preference_weight
        self.risk_weight = risk_weight

    def score(
        self,
        listing: NormalizedListing,
        enrichment: EnrichedListing,
        market_stats: MarketStats,
        preferences: PreferenceProfile,
    ) -> ScoringBreakdown:
        """
        Calculate full scoring breakdown for a listing.

        Args:
            listing: The listing to score
            enrichment: Extracted attributes and risks
            market_stats: Market comparison data
            preferences: User preferences

        Returns:
            ScoringBreakdown with all components
        """
        value_score = self._calculate_value_score(listing, market_stats)
        pref_score = self._calculate_preference_score(listing, enrichment, preferences)
        risk_score = self._calculate_risk_score(enrichment)

        # Weighted total
        total = (
            value_score.score * self.value_weight
            + pref_score.score * self.preference_weight
            + risk_score.score * self.risk_weight
        )

        # Build summary
        summary = self._build_summary(value_score, pref_score, risk_score)

        return ScoringBreakdown(
            total=round(total, 1),
            value_score=value_score,
            preference_score=pref_score,
            risk_score=risk_score,
            value_weight=self.value_weight,
            preference_weight=self.preference_weight,
            risk_weight=self.risk_weight,
            summary_explanation=summary,
        )

    def _calculate_value_score(
        self,
        listing: NormalizedListing,
        market_stats: MarketStats,
    ) -> ValueScore:
        """Calculate value score based on price vs market."""
        if not listing.price or not market_stats.is_sufficient:
            return ValueScore(
                score=50.0,  # Neutral if no comparison possible
                asking_price=listing.price or 0,
                expected_price=market_stats.median,
                deal_delta=0,
                deal_delta_percent=0,
                explanation="Otillräckliga jämförelseobjekt för prisanalys",
            )

        asking = listing.price
        expected = market_stats.median
        
        # Calculate delta (positive = below market = good deal)
        delta = expected - asking
        delta_percent = (delta / expected * 100) if expected > 0 else 0

        # Score based on delta percentage
        # -30% or worse = 0 points
        # 0% = 50 points  
        # +30% or better = 100 points
        score = 50 + (delta_percent * 50 / 30)
        score = max(0, min(100, score))

        # Explanation
        if delta_percent > 10:
            explanation = f"Bra pris! {abs(delta_percent):.0f}% under marknad"
        elif delta_percent < -10:
            explanation = f"Högt pris - {abs(delta_percent):.0f}% över marknad"
        else:
            explanation = "Marknadsmässigt pris"

        return ValueScore(
            score=round(score, 1),
            asking_price=asking,
            expected_price=expected,
            deal_delta=round(delta, 0),
            deal_delta_percent=round(delta_percent, 1),
            explanation=explanation,
        )

    def _calculate_preference_score(
        self,
        listing: NormalizedListing,
        enrichment: EnrichedListing,
        preferences: PreferenceProfile,
    ) -> PreferenceScore:
        """Calculate how well listing matches preferences."""
        matched = []
        unmatched = []
        penalties = []
        total_weight = 0
        matched_weight = 0

        for pref in preferences.selected_preferences:
            total_weight += 1
            extracted_val = enrichment.get_attribute_value(pref.attribute)

            if extracted_val is None:
                penalties.append(f"{pref.attribute}: okänt")
                continue

            if self._preference_matches(pref.value, extracted_val, pref.constraint_type):
                matched.append(pref.attribute)
                matched_weight += 1
            else:
                unmatched.append(pref.attribute)

        # Base score from matches
        if total_weight > 0:
            base_score = (matched_weight / total_weight) * 100
        else:
            base_score = 80  # No preferences = slightly below neutral

        # Penalty for missing info
        missing_penalty = len(enrichment.missing_fields) * 5
        score = max(0, base_score - missing_penalty)

        # Explanation
        if matched:
            explanation = f"Matchar: {', '.join(matched[:3])}"
            if unmatched:
                explanation += f". Missmatch: {', '.join(unmatched[:2])}"
        else:
            explanation = "Få preferenser att matcha"

        return PreferenceScore(
            score=round(score, 1),
            matched_preferences=matched,
            unmatched_preferences=unmatched,
            missing_info_penalties=penalties,
            explanation=explanation,
        )

    def _preference_matches(
        self,
        pref_value: any,
        actual_value: any,
        constraint_type: str,
    ) -> bool:
        """Check if actual value matches preference."""
        if constraint_type == "equals":
            return str(pref_value).lower() == str(actual_value).lower()
        elif constraint_type == "min":
            try:
                return float(actual_value) >= float(pref_value)
            except (ValueError, TypeError):
                return False
        elif constraint_type == "max":
            try:
                return float(actual_value) <= float(pref_value)
            except (ValueError, TypeError):
                return False
        elif constraint_type == "in":
            if isinstance(pref_value, list):
                return str(actual_value).lower() in [str(v).lower() for v in pref_value]
            return False
        elif constraint_type == "contains":
            return str(pref_value).lower() in str(actual_value).lower()
        return False

    def _calculate_risk_score(self, enrichment: EnrichedListing) -> RiskScore:
        """Calculate risk score (higher = less risky)."""
        if not enrichment.risk_flags:
            return RiskScore(
                score=100.0,
                risk_flags=[],
                explanation="Inga riskflaggor upptäckta",
            )

        # Calculate total risk from flags
        total_severity = sum(f.severity for f in enrichment.risk_flags)
        
        # Each flag reduces score
        # Max 100 points, lose up to 20 per flag based on severity
        penalty = min(100, total_severity * 30)
        score = 100 - penalty

        flag_names = [f.flag_type for f in enrichment.risk_flags]

        if score < 50:
            explanation = f"Hög risk: {', '.join(flag_names)}"
        elif score < 75:
            explanation = f"Viss osäkerhet: {len(enrichment.risk_flags)} flaggor"
        else:
            explanation = "Låg risk"

        return RiskScore(
            score=round(score, 1),
            risk_flags=flag_names,
            explanation=explanation,
        )

    def _build_summary(
        self,
        value: ValueScore,
        pref: PreferenceScore,
        risk: RiskScore,
    ) -> str:
        """Build one-line summary explanation."""
        parts = []

        if value.deal_delta_percent > 10:
            parts.append(f"🟢 Bra pris ({value.deal_delta_percent:.0f}% under)")
        elif value.deal_delta_percent < -10:
            parts.append(f"🔴 Högt pris")
        
        if pref.score >= 80:
            parts.append("✓ Bra match")
        elif pref.score < 50:
            parts.append("⚠ Svag match")

        if risk.score < 50:
            parts.append("⚠ Risker")

        return " | ".join(parts) if parts else "Genomsnittligt alternativ"

    def rank_listings(
        self,
        listings: list[NormalizedListing],
        enrichments: list[EnrichedListing],
        market_stats_map: dict[str, MarketStats],
        preferences: PreferenceProfile,
        top_k: int = 10,
    ) -> list[RankedListing]:
        """
        Score and rank all listings.

        Args:
            listings: All listings to rank
            enrichments: Enrichment data per listing
            market_stats_map: Market stats by listing_id
            preferences: User preferences
            top_k: Number of top results to return

        Returns:
            Sorted list of RankedListing objects
        """
        enrichment_map = {e.listing_id: e for e in enrichments}
        scored = []

        for listing in listings:
            enrichment = enrichment_map.get(listing.listing_id)
            if not enrichment:
                continue

            market_stats = market_stats_map.get(listing.listing_id)
            if not market_stats:
                market_stats = MarketStats(
                    median=0, iqr=0, q1=0, q3=0,
                    min_price=0, max_price=0, n=0,
                    is_sufficient=False,
                )

            scores = self.score(listing, enrichment, market_stats, preferences)

            scored.append((listing, enrichment, market_stats, scores))

        # Sort by total score descending
        scored.sort(key=lambda x: x[3].total, reverse=True)

        # Build RankedListing objects
        ranked = []
        for rank, (listing, enrichment, market_stats, scores) in enumerate(scored[:top_k], 1):
            ranked.append(RankedListing(
                rank=rank,
                listing=listing,
                enrichment=enrichment,
                market_stats=market_stats,
                scores=scores,
            ))

        return ranked
