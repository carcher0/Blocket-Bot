"""
Comps module: Build comparable groups of listings for fair price comparison.
"""
from typing import Optional
from collections import defaultdict

from .schemas import (
    CompsGroup,
    CompsStats,
    CanonicalKey,
    ExtractedAttributes,
)


def compute_comps_stats(prices: list[float]) -> Optional[CompsStats]:
    """
    Compute robust statistics for a group of prices.
    
    Uses median and IQR for robustness against outliers.
    """
    if not prices:
        return None
    
    prices = sorted(prices)
    n = len(prices)
    
    # Median
    if n % 2 == 0:
        median = (prices[n // 2 - 1] + prices[n // 2]) / 2
    else:
        median = prices[n // 2]
    
    # Quartiles
    def quartile(data: list[float], q: float) -> float:
        idx = (len(data) - 1) * q
        lower = int(idx)
        upper = lower + 1
        if upper >= len(data):
            return data[lower]
        return data[lower] + (idx - lower) * (data[upper] - data[lower])
    
    q1 = quartile(prices, 0.25)
    q3 = quartile(prices, 0.75)
    iqr = q3 - q1
    
    return CompsStats(
        median_price=median,
        iqr=iqr,
        q1=q1,
        q3=q3,
        min_price=min(prices),
        max_price=max(prices),
        n=n,
    )


def build_comps_groups(
    listings: list[dict],
    attributes_map: dict[str, ExtractedAttributes],
    canonical_keys: dict[str, CanonicalKey],
    min_sample: int = 5,
) -> list[CompsGroup]:
    """
    Build comparison groups from listings.
    
    Args:
        listings: List of normalized listing dicts
        attributes_map: listing_id -> ExtractedAttributes
        canonical_keys: listing_id -> CanonicalKey
        min_sample: Minimum sample size for a valid comps group
        
    Returns:
        List of CompsGroup with statistics
    """
    # Group listings by canonical key
    groups: dict[tuple, list[dict]] = defaultdict(list)
    
    for listing in listings:
        listing_id = str(listing.get("listing_id", ""))
        if listing_id not in canonical_keys:
            continue
        
        key = canonical_keys[listing_id]
        key_tuple = key.to_tuple()
        groups[key_tuple].append(listing)
    
    # Build CompsGroup for each
    result = []
    for key_tuple, group_listings in groups.items():
        # Extract prices
        prices = []
        listing_ids = []
        for listing in group_listings:
            price = listing.get("price", {})
            if isinstance(price, dict):
                amount = price.get("amount")
            else:
                amount = None
            
            if amount and amount > 0:
                prices.append(float(amount))
                listing_ids.append(str(listing.get("listing_id", "")))
        
        if not prices:
            continue
        
        # Compute stats
        stats = compute_comps_stats(prices)
        
        # Create canonical key from tuple
        family, model, storage, condition = key_tuple
        canonical_key = CanonicalKey(
            family=family,
            model_variant=model,
            storage_bucket=storage,
            condition_bucket=condition,
        )
        
        comps_group = CompsGroup(
            comps_key=canonical_key,
            listing_ids=listing_ids,
            stats=stats,
            is_sufficient=len(prices) >= min_sample,
            relaxation_level=0,
        )
        result.append(comps_group)
    
    return result


def relax_comps_key(key: CanonicalKey, level: int) -> CanonicalKey:
    """
    Relax a canonical key by dropping dimensions.
    
    Level 0: Full key
    Level 1: Drop condition_bucket
    Level 2: Drop storage_bucket
    Level 3: Drop model_variant (just family)
    """
    if level == 0:
        return key
    elif level == 1:
        return CanonicalKey(
            family=key.family,
            model_variant=key.model_variant,
            storage_bucket=key.storage_bucket,
            condition_bucket=None,
        )
    elif level == 2:
        return CanonicalKey(
            family=key.family,
            model_variant=key.model_variant,
            storage_bucket=None,
            condition_bucket=None,
        )
    else:
        return CanonicalKey(
            family=key.family,
            model_variant=None,
            storage_bucket=None,
            condition_bucket=None,
        )


def find_comps_for_listing(
    listing_id: str,
    canonical_key: CanonicalKey,
    all_groups: list[CompsGroup],
    min_sample: int = 5,
) -> tuple[Optional[CompsGroup], int]:
    """
    Find the best comps group for a listing.
    
    First tries exact match, then progressively relaxes the key.
    
    Returns:
        (CompsGroup, relaxation_level) or (None, -1) if none found
    """
    for level in range(4):
        relaxed_key = relax_comps_key(canonical_key, level)
        
        for group in all_groups:
            group_key = relax_comps_key(group.comps_key, level)
            
            if (group_key.family == relaxed_key.family and
                group_key.model_variant == relaxed_key.model_variant and
                group_key.storage_bucket == relaxed_key.storage_bucket and
                group_key.condition_bucket == relaxed_key.condition_bucket):
                
                if group.stats and group.stats.n >= min_sample:
                    return (group, level)
    
    return (None, -1)
