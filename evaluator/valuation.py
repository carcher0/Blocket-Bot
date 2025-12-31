"""
Valuation module: Compute market price estimates using robust statistics.
"""
from typing import Optional

from .schemas import CompsStats, CompsGroup


def compute_expected_price(comps: CompsGroup) -> Optional[float]:
    """
    Get the expected (fair market) price from a comps group.
    Uses median as the robust estimate.
    """
    if comps.stats:
        return comps.stats.median_price
    return None


def compute_deal_delta(asking_price: float, expected_price: float) -> float:
    """
    Compute how good of a deal this is.
    
    deal_delta = (expected - asking) / expected
    
    Positive = good deal (below market)
    Negative = overpriced (above market)
    Zero = at market price
    """
    if expected_price <= 0:
        return 0.0
    return (expected_price - asking_price) / expected_price


def is_price_outlier(price: float, stats: CompsStats, iqr_multiplier: float = 1.5) -> bool:
    """
    Check if a price is an outlier using IQR method.
    
    Outlier if price < Q1 - 1.5*IQR or price > Q3 + 1.5*IQR
    """
    lower_bound = stats.q1 - iqr_multiplier * stats.iqr
    upper_bound = stats.q3 + iqr_multiplier * stats.iqr
    return price < lower_bound or price > upper_bound


def is_suspiciously_low(price: float, stats: CompsStats, iqr_multiplier: float = 1.5) -> bool:
    """
    Check if price is suspiciously low (potential red flag).
    """
    lower_bound = stats.q1 - iqr_multiplier * stats.iqr
    return price < lower_bound


def price_percentile(price: float, stats: CompsStats) -> float:
    """
    Estimate what percentile this price falls in.
    
    Returns 0-100 where lower is better deal.
    """
    if stats.iqr == 0:
        if price < stats.median_price:
            return 25.0
        elif price > stats.median_price:
            return 75.0
        else:
            return 50.0
    
    # Approximate using position relative to quartiles
    if price <= stats.q1:
        # Below Q1: 0-25%
        if price <= stats.min_price:
            return 0.0
        ratio = (price - stats.min_price) / (stats.q1 - stats.min_price) if stats.q1 > stats.min_price else 0
        return ratio * 25
    elif price <= stats.median_price:
        # Q1 to median: 25-50%
        ratio = (price - stats.q1) / (stats.median_price - stats.q1) if stats.median_price > stats.q1 else 0
        return 25 + ratio * 25
    elif price <= stats.q3:
        # Median to Q3: 50-75%
        ratio = (price - stats.median_price) / (stats.q3 - stats.median_price) if stats.q3 > stats.median_price else 0
        return 50 + ratio * 25
    else:
        # Above Q3: 75-100%
        if price >= stats.max_price:
            return 100.0
        ratio = (price - stats.q3) / (stats.max_price - stats.q3) if stats.max_price > stats.q3 else 0
        return 75 + ratio * 25


def format_price_context(stats: CompsStats) -> str:
    """
    Format comps stats as human-readable context.
    """
    return (
        f"Marknadspris: {stats.median_price:,.0f} kr (median)\n"
        f"Spann: {stats.q1:,.0f} - {stats.q3:,.0f} kr (25-75%)\n"
        f"Baserat på {stats.n} jämförbara annonser"
    )
