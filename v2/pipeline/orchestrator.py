"""
Pipeline orchestrator - runs the full evaluation pipeline.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from ..config import get_config
from ..models.listing import NormalizedListing
from ..models.preferences import PreferenceProfile
from ..models.discovery import DomainDiscoveryOutput, DEFAULT_GENERIC_SCHEMA
from ..models.scoring import RankedListing
from ..models.export import RunMetadata, FullRunExport

from .filter import CandidateFilter
from .enrichment import ListingEnricher
from .comps import CompsCalculator
from .scoring import ScoringEngine


logger = logging.getLogger(__name__)


def run_pipeline(
    listings: list[NormalizedListing],
    preferences: PreferenceProfile,
    schema: Optional[DomainDiscoveryOutput] = None,
    top_k: int = 10,
) -> FullRunExport:
    """
    Run the full evaluation pipeline.

    Pipeline steps:
    1. Filter to top ~50 candidates
    2. Enrich each candidate (extract attributes, detect risks)
    3. Calculate market stats for each
    4. Score and rank
    5. Return top-k results with full export

    Args:
        listings: All fetched listings
        preferences: User preference profile
        schema: Domain schema (uses generic if None)
        top_k: Number of top results to return

    Returns:
        FullRunExport with all results and metadata
    """
    config = get_config()
    run_id = str(uuid.uuid4())[:8]
    started_at = datetime.now()

    logger.info(f"Starting pipeline run {run_id} with {len(listings)} listings")

    # Use generic schema if none provided
    if schema is None:
        schema = DEFAULT_GENERIC_SCHEMA
        logger.info("Using generic fallback schema")

    # Initialize components
    candidate_filter = CandidateFilter(max_candidates=config.pipeline.candidate_limit)
    enricher = ListingEnricher()
    comps_calc = CompsCalculator(min_comps=config.pipeline.min_comps_for_pricing)
    scorer = ScoringEngine()

    # Step 1: Filter to candidates
    logger.info("Step 1: Filtering candidates")
    candidates = candidate_filter.filter(listings, preferences, schema)
    logger.info(f"Filtered to {len(candidates)} candidates")

    # Step 2: Enrich candidates
    logger.info("Step 2: Enriching candidates")
    enrichments = enricher.enrich_batch(candidates, schema)

    # Step 3: Calculate market stats for each candidate
    logger.info("Step 3: Calculating market stats")
    market_stats_map = {}
    for candidate in candidates:
        enrichment = next((e for e in enrichments if e.listing_id == candidate.listing_id), None)
        if enrichment:
            _, stats, _ = comps_calc.find_comps(
                candidate, enrichment, candidates, enrichments
            )
            market_stats_map[candidate.listing_id] = stats

    # Step 4: Score and rank
    logger.info("Step 4: Scoring and ranking")
    ranked = scorer.rank_listings(
        candidates,
        enrichments,
        market_stats_map,
        preferences,
        top_k=top_k,
    )

    # Build metadata
    completed_at = datetime.now()
    metadata = RunMetadata(
        run_id=run_id,
        started_at=started_at,
        completed_at=completed_at,
        user_query=preferences.user_query,
        total_listings_fetched=len(listings),
        listings_after_filter=len(candidates),
        listings_enriched=len(enrichments),
    )

    # Market summary
    all_prices = [l.price for l in listings if l.price and l.price > 0]
    market_summary = {}
    if all_prices:
        import numpy as np
        market_summary = {
            "total_listings": len(listings),
            "with_price": len(all_prices),
            "median_price": float(np.median(all_prices)),
            "min_price": float(min(all_prices)),
            "max_price": float(max(all_prices)),
        }

    # Build export
    export = FullRunExport(
        metadata=metadata,
        discovery_schema=schema,
        preferences=preferences,
        top_results=ranked,
        market_summary=market_summary,
    )

    logger.info(f"Pipeline completed: {len(ranked)} top results")
    return export


def run_quick_evaluation(
    listings: list[NormalizedListing],
    user_query: str,
    max_price: Optional[float] = None,
    top_k: int = 10,
) -> list[RankedListing]:
    """
    Simplified pipeline for quick evaluations.
    Uses generic schema and minimal preferences.
    """
    preferences = PreferenceProfile(
        user_query=user_query,
        max_price=max_price,
    )

    export = run_pipeline(
        listings=listings,
        preferences=preferences,
        schema=None,
        top_k=top_k,
    )

    return export.top_results
