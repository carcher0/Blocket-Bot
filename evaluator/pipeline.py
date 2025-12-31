"""
Main evaluation pipeline: Orchestrates all evaluation steps.
"""
from typing import Optional
from datetime import datetime

from .schemas import (
    EvaluationResult,
    QueryAnalysisResult,
    RankedListing,
    ExtractedAttributes,
    CanonicalKey,
    CompsGroup,
    ClarifyingQuestion,
    ProductFamily,
)
from .query_analyzer import analyze_query, should_filter_accessories
from .attribute_packs.phone_pack import PhonePack
from .comps import build_comps_groups, find_comps_for_listing
from .scoring import score_listing


# Attribute pack registry
ATTRIBUTE_PACKS = {
    ProductFamily.PHONE: PhonePack(),
}


def run_evaluation(
    query: str,
    listings: list[dict],
    preferences: dict,
    watch_id: Optional[str] = None,
    filter_accessories: bool = True,
    min_comps_sample: int = 5,
    top_k: int = 10,
) -> EvaluationResult:
    """
    Run the full evaluation pipeline on a set of listings.
    
    Args:
        query: Search query string
        listings: Normalized listings from BlocketAPI
        preferences: User preferences dict
        watch_id: Optional watch ID for tracking
        filter_accessories: Whether to filter out accessory listings
        min_comps_sample: Minimum sample size for valid comps
        top_k: Number of top results to include
        
    Returns:
        EvaluationResult with ranked listings and analysis
    """
    # Step 1: Query Analysis
    probe_sample = listings[:50] if len(listings) > 50 else listings
    query_analysis = analyze_query(query, probe_sample)
    
    # Filter accessories if requested
    working_listings = listings
    if filter_accessories:
        working_listings = should_filter_accessories(listings)
    
    filtered_out = len(listings) - len(working_listings)
    
    # Get appropriate attribute pack
    pack = ATTRIBUTE_PACKS.get(query_analysis.product_family)
    if not pack:
        # Default to phone pack for now
        pack = PhonePack()
    
    # Step 2: Attribute Extraction
    attributes_map: dict[str, ExtractedAttributes] = {}
    canonical_keys: dict[str, CanonicalKey] = {}
    
    for listing in working_listings:
        listing_id = str(listing.get("listing_id", ""))
        if not listing_id:
            continue
        
        attrs = pack.extract(listing)
        attributes_map[listing_id] = attrs
        canonical_keys[listing_id] = pack.create_canonical_key(attrs)
    
    # Step 3-4: Build Comps Groups
    comps_groups = build_comps_groups(
        working_listings,
        attributes_map,
        canonical_keys,
        min_sample=min_comps_sample,
    )
    
    # Step 5-6: Score each listing
    scored_listings: list[tuple[dict, ExtractedAttributes, Optional[CompsGroup], float]] = []
    
    for listing in working_listings:
        listing_id = str(listing.get("listing_id", ""))
        if listing_id not in attributes_map:
            continue
        
        attrs = attributes_map[listing_id]
        canonical_key = canonical_keys.get(listing_id)
        
        # Find best comps group
        comps_group = None
        if canonical_key:
            comps_group, _ = find_comps_for_listing(
                listing_id,
                canonical_key,
                comps_groups,
                min_sample=min_comps_sample,
            )
        
        # Score the listing
        scores = score_listing(listing, attrs, comps_group, preferences)
        
        # Skip if hard filters failed
        if not scores.preference_score.hard_filters_passed:
            filtered_out += 1
            continue
        
        scored_listings.append((listing, attrs, comps_group, scores.final_score))
    
    # Sort by final score (descending)
    scored_listings.sort(key=lambda x: x[3], reverse=True)
    
    # Build ranked listings
    ranked_listings: list[RankedListing] = []
    
    for rank, (listing, attrs, comps, final_score) in enumerate(scored_listings[:top_k], 1):
        listing_id = str(listing.get("listing_id", ""))
        
        # Re-compute scores for details
        scores = score_listing(listing, attrs, comps, preferences)
        
        # Generate checklist from missing info
        checklist = []
        missing = pack.get_missing_key_attributes(attrs)
        for attr in missing:
            checklist.append(f"Fråga säljaren om: {attr.replace('_', ' ')}")
        
        # Get price
        price_data = listing.get("price", {})
        asking_price = price_data.get("amount") if isinstance(price_data, dict) else None
        
        ranked_listing = RankedListing(
            listing_id=listing_id,
            url=listing.get("url", ""),
            title=listing.get("title"),
            asking_price=asking_price,
            location=listing.get("location"),
            attributes=attrs,
            canonical_key=canonical_keys.get(listing_id),
            scores=scores,
            checklist=checklist,
            rank=rank,
        )
        ranked_listings.append(ranked_listing)
    
    # Generate clarifying questions if ambiguous
    questions: list[ClarifyingQuestion] = []
    if query_analysis.is_ambiguous and query_analysis.clarifying_question:
        questions.append(ClarifyingQuestion(
            question=query_analysis.clarifying_question,
            options=query_analysis.clarifying_options,
            reason="Sökningen innehåller blandade produkttyper",
            information_gain=0.8,
        ))
    
    # Data quality notes
    data_quality_notes = []
    if len(comps_groups) == 0:
        data_quality_notes.append("Kunde inte bygga jämförelsegrupper (för få annonser eller för olika)")
    if filtered_out > len(listings) * 0.5:
        data_quality_notes.append(f"Många annonser filtrerades bort ({filtered_out} av {len(listings)})")
    
    return EvaluationResult(
        query=query,
        watch_id=watch_id,
        evaluated_at=datetime.utcnow().isoformat() + "Z",
        query_analysis=query_analysis,
        ranked_listings=ranked_listings,
        total_evaluated=len(scored_listings),
        filtered_out=filtered_out,
        comps_groups=comps_groups,
        questions=questions,
        data_quality_notes=data_quality_notes,
    )


def evaluate_single_listing(
    listing: dict,
    all_listings: list[dict],
    preferences: dict,
    product_family: ProductFamily = ProductFamily.PHONE,
) -> RankedListing:
    """
    Evaluate a single listing against a set of comparable listings.
    Useful for quick checks on individual ads.
    """
    # Get attribute pack
    pack = ATTRIBUTE_PACKS.get(product_family, PhonePack())
    
    # Extract attributes for all listings
    attributes_map = {}
    canonical_keys = {}
    
    for l in all_listings + [listing]:
        lid = str(l.get("listing_id", ""))
        if lid:
            attrs = pack.extract(l)
            attributes_map[lid] = attrs
            canonical_keys[lid] = pack.create_canonical_key(attrs)
    
    # Build comps
    comps_groups = build_comps_groups(all_listings, attributes_map, canonical_keys)
    
    # Score the target listing
    listing_id = str(listing.get("listing_id", ""))
    attrs = attributes_map.get(listing_id, pack.extract(listing))
    canonical_key = canonical_keys.get(listing_id)
    
    comps_group = None
    if canonical_key:
        comps_group, _ = find_comps_for_listing(listing_id, canonical_key, comps_groups)
    
    scores = score_listing(listing, attrs, comps_group, preferences)
    
    price_data = listing.get("price", {})
    asking_price = price_data.get("amount") if isinstance(price_data, dict) else None
    
    return RankedListing(
        listing_id=listing_id,
        url=listing.get("url", ""),
        title=listing.get("title"),
        asking_price=asking_price,
        location=listing.get("location"),
        attributes=attrs,
        canonical_key=canonical_key,
        scores=scores,
        rank=1,
    )
