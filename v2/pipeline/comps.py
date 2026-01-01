"""
Comps calculator - compute market statistics for comparable groups.
"""
import logging
from typing import Optional

import numpy as np

from ..models.listing import NormalizedListing
from ..models.enrichment import EnrichedListing
from ..models.scoring import MarketStats


logger = logging.getLogger(__name__)


class CompsCalculator:
    """
    Calculates market statistics for comparable listing groups.
    Supports relaxation when groups are too small.
    """

    def __init__(self, min_comps: int = 3):
        """
        Args:
            min_comps: Minimum number of comps for reliable stats
        """
        self.min_comps = min_comps

    def calculate(
        self,
        listings: list[NormalizedListing],
        enrichments: list[EnrichedListing],
        target_listing_id: Optional[str] = None,
    ) -> MarketStats:
        """
        Calculate market stats for a group of listings.

        Args:
            listings: Listings to analyze
            enrichments: Corresponding enrichment data
            target_listing_id: If provided, exclude from stats

        Returns:
            MarketStats with computed statistics
        """
        # Get prices, excluding target if specified
        prices = []
        for listing in listings:
            if target_listing_id and listing.listing_id == target_listing_id:
                continue
            if listing.price and listing.price > 0:
                prices.append(listing.price)

        if not prices:
            return MarketStats(
                median=0,
                iqr=0,
                q1=0,
                q3=0,
                min_price=0,
                max_price=0,
                n=0,
                is_sufficient=False,
            )

        prices_array = np.array(prices)

        median = float(np.median(prices_array))
        q1 = float(np.percentile(prices_array, 25))
        q3 = float(np.percentile(prices_array, 75))
        iqr = q3 - q1

        return MarketStats(
            median=median,
            iqr=iqr,
            q1=q1,
            q3=q3,
            min_price=float(np.min(prices_array)),
            max_price=float(np.max(prices_array)),
            n=len(prices),
            is_sufficient=len(prices) >= self.min_comps,
        )

    def find_comps(
        self,
        target: NormalizedListing,
        target_enrichment: EnrichedListing,
        all_listings: list[NormalizedListing],
        all_enrichments: list[EnrichedListing],
        key_attributes: list[str] = None,
    ) -> tuple[list[NormalizedListing], MarketStats, int]:
        """
        Find comparable listings for a target and calculate stats.
        Uses progressive relaxation if needed.

        Args:
            target: The target listing
            target_enrichment: Target's enrichment
            all_listings: All available listings
            all_enrichments: All enrichment data
            key_attributes: Attributes to use for grouping

        Returns:
            Tuple of (comp_listings, market_stats, relaxation_level)
        """
        if key_attributes is None:
            key_attributes = ["storage_gb", "condition"]

        # Build enrichment lookup
        enrichment_map = {e.listing_id: e for e in all_enrichments}

        # Progressive relaxation levels
        for relaxation in range(len(key_attributes) + 1):
            attrs_to_match = key_attributes[relaxation:]
            
            comps = self._find_matching_listings(
                target,
                target_enrichment,
                all_listings,
                enrichment_map,
                attrs_to_match,
            )

            if len(comps) >= self.min_comps:
                stats = self.calculate(comps, [], target.listing_id)
                stats.relaxation_level = relaxation
                stats.comp_key = self._build_comp_key(target_enrichment, attrs_to_match)
                return comps, stats, relaxation

        # No sufficient comps found - use all listings
        stats = self.calculate(all_listings, [], target.listing_id)
        stats.is_sufficient = False
        stats.relaxation_level = len(key_attributes)
        stats.comp_key = "all"
        return all_listings, stats, len(key_attributes)

    def _find_matching_listings(
        self,
        target: NormalizedListing,
        target_enrichment: EnrichedListing,
        all_listings: list[NormalizedListing],
        enrichment_map: dict[str, EnrichedListing],
        attributes: list[str],
    ) -> list[NormalizedListing]:
        """Find listings that match target on specified attributes."""
        matches = []

        # Get target attribute values
        target_values = {}
        for attr in attributes:
            val = target_enrichment.get_attribute_value(attr)
            if val is not None:
                target_values[attr] = val

        for listing in all_listings:
            if listing.listing_id == target.listing_id:
                continue

            enrichment = enrichment_map.get(listing.listing_id)
            if not enrichment:
                continue

            # Check if all required attributes match
            matches_all = True
            for attr, target_val in target_values.items():
                listing_val = enrichment.get_attribute_value(attr)
                if listing_val is None:
                    matches_all = False
                    break
                if not self._values_match(target_val, listing_val, attr):
                    matches_all = False
                    break

            if matches_all:
                matches.append(listing)

        return matches

    def _values_match(self, val1: any, val2: any, attr: str) -> bool:
        """Check if two attribute values should be considered matching."""
        if val1 == val2:
            return True

        # Storage: exact match required
        if attr == "storage_gb":
            return val1 == val2

        # Condition: fuzzy matching
        if attr == "condition":
            condition_order = ["ny", "nyskick", "som ny", "like new", "bra", "good", "ok", "defekt"]
            try:
                idx1 = next((i for i, c in enumerate(condition_order) if c in str(val1).lower()), -1)
                idx2 = next((i for i, c in enumerate(condition_order) if c in str(val2).lower()), -1)
                # Allow 1 step difference
                return abs(idx1 - idx2) <= 1
            except (ValueError, TypeError):
                pass

        return val1 == val2

    def _build_comp_key(
        self,
        enrichment: EnrichedListing,
        attributes: list[str],
    ) -> str:
        """Build a string key representing the comp group."""
        parts = []
        for attr in attributes:
            val = enrichment.get_attribute_value(attr)
            if val is not None:
                parts.append(f"{attr}={val}")
        return "|".join(parts) if parts else "all"
