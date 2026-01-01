"""
Main evaluation pipeline: Orchestrates all evaluation steps.
AI-First approach: Filter irrelevant listings BEFORE scoring.
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
    ClusterInfo,
)
from .ai_filter import filter_and_prepare_listings, QueryUnderstanding
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
    use_ai_filter: bool = True,
    min_comps_sample: int = 3,  # Lowered for better matching
    top_k: int = 10,
) -> EvaluationResult:
    """
    Run the full AI-first evaluation pipeline.
    
    NEW FLOW:
    1. AI understands query
    2. AI filters irrelevant listings (cases, services, wrong models)
    3. Deduplicate
    4. Extract attributes
    5. Build comps from ONLY relevant listings
    6. Score and rank
    
    Args:
        query: Search query string
        listings: Normalized listings from BlocketAPI
        preferences: User preferences dict
        watch_id: Optional watch ID for tracking
        use_ai_filter: Whether to use GPT-5.2 for relevance filtering
        min_comps_sample: Minimum sample size for valid comps
        top_k: Number of top results to include
        
    Returns:
        EvaluationResult with ranked listings and analysis
    """
    original_count = len(listings)
    
    # ====== STEP 1-3: AI FILTERING (NEW) ======
    if use_ai_filter:
        # AI understands query, filters irrelevant, deduplicates
        working_listings, query_understanding = filter_and_prepare_listings(listings, query)
    else:
        # Fallback: basic filtering
        working_listings = listings
        query_understanding = QueryUnderstanding(
            product_type="other",
            brand=None,
            model_line=query,
            model_variant=None,
            must_match_keywords=query.lower().split(),
            exclude_keywords=[],
            expected_price_min=None,
            expected_price_max=None,
        )
    
    filtered_out = original_count - len(working_listings)
    
    # Build query analysis from understanding
    query_analysis = QueryAnalysisResult(
        query=query,
        product_family=_map_product_type(query_understanding.product_type),
        confidence=0.9 if use_ai_filter else 0.5,
        key_attributes=["model_variant", "storage_gb", "condition", "battery_health"],
        clusters=[],
        is_ambiguous=False,
        probe_sample_size=original_count,
    )
    
    # Get appropriate attribute pack
    pack = ATTRIBUTE_PACKS.get(query_analysis.product_family)
    if not pack:
        pack = PhonePack()
    
    # ====== STEP 4: ATTRIBUTE EXTRACTION ======
    attributes_map: dict[str, ExtractedAttributes] = {}
    canonical_keys: dict[str, CanonicalKey] = {}
    
    for listing in working_listings:
        listing_id = str(listing.get("listing_id", ""))
        if not listing_id:
            continue
        
        # Try LLM fallback for better extraction
        attrs = pack.extract(listing, use_llm_fallback=True)
        attributes_map[listing_id] = attrs
        canonical_keys[listing_id] = pack.create_canonical_key(attrs)
    
    # ====== STEP 5: BUILD COMPS ======
    comps_groups = build_comps_groups(
        working_listings,
        attributes_map,
        canonical_keys,
        min_sample=min_comps_sample,
    )
    
    # ====== STEP 6: SCORE EACH LISTING ======
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
        
        scores = score_listing(listing, attrs, comps, preferences)
        
        # Generate checklist from missing info
        checklist = []
        missing = pack.get_missing_key_attributes(attrs)
        for attr in missing:
            checklist.append(f"Fråga säljaren om: {attr.replace('_', ' ')}")
        
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
    
    # Data quality notes
    data_quality_notes = []
    if use_ai_filter:
        data_quality_notes.append(f"✅ AI filtrerade bort {filtered_out} irrelevanta annonser")
    if len(comps_groups) == 0:
        data_quality_notes.append("⚠️ Få jämförbara annonser - prisdata osäker")
    if len(working_listings) < 5:
        data_quality_notes.append("⚠️ Endast få relevanta annonser hittades")
    
    return EvaluationResult(
        query=query,
        watch_id=watch_id,
        evaluated_at=datetime.utcnow().isoformat() + "Z",
        query_analysis=query_analysis,
        ranked_listings=ranked_listings,
        total_evaluated=len(scored_listings),
        filtered_out=filtered_out,
        comps_groups=comps_groups,
        questions=[],
        data_quality_notes=data_quality_notes,
    )


def _map_product_type(product_type: str) -> ProductFamily:
    """Map AI product type string to ProductFamily enum."""
    mapping = {
        "smartphone": ProductFamily.PHONE,
        "laptop": ProductFamily.LAPTOP,
        "tablet": ProductFamily.TABLET,
        "camera": ProductFamily.CAMERA,
    }
    return mapping.get(product_type, ProductFamily.UNKNOWN)


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
