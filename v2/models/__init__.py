"""
Pydantic models for Blocket Bot v2.
All data contracts are defined here for strict validation.
"""

from .listing import Listing, NormalizedListing
from .discovery import (
    AttributeCandidate,
    PreferenceQuestion,
    DomainDiscoveryOutput,
)
from .preferences import PreferenceProfile
from .enrichment import EnrichedListing
from .scoring import MarketStats, ScoringBreakdown, RankedListing
from .export import RunMetadata, FullRunExport

__all__ = [
    # Listing
    "Listing",
    "NormalizedListing",
    # Discovery
    "AttributeCandidate",
    "PreferenceQuestion", 
    "DomainDiscoveryOutput",
    # Preferences
    "PreferenceProfile",
    # Enrichment
    "EnrichedListing",
    # Scoring
    "MarketStats",
    "ScoringBreakdown",
    "RankedListing",
    # Export
    "RunMetadata",
    "FullRunExport",
]
