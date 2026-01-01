"""
Candidate filter - reduce listings to top candidates before expensive enrichment.
"""
import re
import logging
from typing import Optional

import numpy as np

from ..models.listing import NormalizedListing
from ..models.preferences import PreferenceProfile
from ..models.discovery import DomainDiscoveryOutput


logger = logging.getLogger(__name__)


class CandidateFilter:
    """
    Filters listings to top candidates using lexical matching,
    price sanity checks, and hard constraint filtering.
    """

    def __init__(self, max_candidates: int = 50):
        self.max_candidates = max_candidates

    def filter(
        self,
        listings: list[NormalizedListing],
        preferences: PreferenceProfile,
        schema: Optional[DomainDiscoveryOutput] = None,
    ) -> list[NormalizedListing]:
        """
        Filter listings to top candidates.

        Args:
            listings: All fetched listings
            preferences: User preference profile
            schema: Domain discovery schema (for context)

        Returns:
            Filtered list of top candidates
        """
        logger.info(f"Filtering {len(listings)} listings to max {self.max_candidates}")

        if not listings:
            return []

        # Step 1: Apply hard constraints
        filtered = self._apply_hard_constraints(listings, preferences)
        logger.info(f"After hard constraints: {len(filtered)} listings")

        # Step 2: Price sanity filter (remove extreme outliers, but keep potential deals)
        filtered = self._price_sanity_filter(filtered)
        logger.info(f"After price sanity: {len(filtered)} listings")

        # Step 3: Relevance scoring
        scored = self._score_relevance(filtered, preferences.user_query)

        # Step 4: Sort by relevance and take top candidates
        scored.sort(key=lambda x: x[1], reverse=True)
        candidates = [listing for listing, score in scored[: self.max_candidates]]

        logger.info(f"Final candidates: {len(candidates)}")
        return candidates

    def _apply_hard_constraints(
        self,
        listings: list[NormalizedListing],
        preferences: PreferenceProfile,
    ) -> list[NormalizedListing]:
        """Apply hard constraints to filter out non-matching listings."""
        filtered = []

        for listing in listings:
            # Price constraints
            if preferences.max_price and listing.price:
                if listing.price > preferences.max_price:
                    continue

            if preferences.min_price and listing.price:
                if listing.price < preferences.min_price:
                    continue

            # Location constraint
            if preferences.locations and listing.location:
                location_lower = listing.location.lower()
                if not any(loc.lower() in location_lower for loc in preferences.locations):
                    continue

            # Shipping constraint
            if preferences.require_shipping:
                if not listing.shipping_available:
                    continue

            filtered.append(listing)

        return filtered

    def _price_sanity_filter(
        self,
        listings: list[NormalizedListing],
        outlier_threshold: float = 3.0,
    ) -> list[NormalizedListing]:
        """
        Remove extreme price outliers but keep potential deals.
        Uses IQR method with generous threshold.
        """
        if len(listings) < 5:
            return listings

        prices = [l.price for l in listings if l.price and l.price > 0]
        if not prices:
            return listings

        # Calculate IQR
        q1 = np.percentile(prices, 25)
        q3 = np.percentile(prices, 75)
        iqr = q3 - q1

        # Generous bounds - keep most listings, only remove extreme outliers
        lower_bound = max(0, q1 - outlier_threshold * iqr)
        upper_bound = q3 + outlier_threshold * iqr

        filtered = []
        for listing in listings:
            if listing.price is None:
                # Keep listings without price
                filtered.append(listing)
            elif lower_bound <= listing.price <= upper_bound:
                filtered.append(listing)
            # Note: we keep items slightly below lower_bound as potential deals

        return filtered

    def _score_relevance(
        self,
        listings: list[NormalizedListing],
        query: str,
    ) -> list[tuple[NormalizedListing, float]]:
        """
        Score listings by relevance to query.
        Uses simple lexical matching for now.
        """
        query_terms = self._tokenize(query)
        scored = []

        for listing in listings:
            score = self._calculate_relevance_score(listing, query_terms)
            scored.append((listing, score))

        return scored

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase terms."""
        return re.findall(r'\w+', text.lower())

    def _calculate_relevance_score(
        self,
        listing: NormalizedListing,
        query_terms: list[str],
    ) -> float:
        """Calculate relevance score for a listing."""
        if not query_terms:
            return 0.5

        text = listing.search_text
        matched = 0
        total_weight = 0

        for term in query_terms:
            weight = len(term)  # Longer terms are more important
            total_weight += weight
            if term in text:
                matched += weight

        if total_weight == 0:
            return 0.0

        base_score = matched / total_weight

        # Bonus for title match
        title_lower = listing.title.lower() if listing.title else ""
        title_bonus = 0
        for term in query_terms:
            if term in title_lower:
                title_bonus += 0.1

        # Bonus for having price
        price_bonus = 0.1 if listing.price else 0

        # Bonus for having images
        image_bonus = min(0.1, listing.image_count * 0.02)

        return min(1.0, base_score + title_bonus + price_bonus + image_bonus)
