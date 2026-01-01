"""
Export models - run metadata and full export structure.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .discovery import DomainDiscoveryOutput
from .preferences import PreferenceProfile
from .scoring import RankedListing


class RunMetadata(BaseModel):
    """Metadata for a pipeline run."""
    run_id: str = Field(description="Unique run identifier")
    started_at: datetime
    completed_at: Optional[datetime] = None
    
    # Query info
    user_query: str
    search_filters: dict[str, Any] = Field(default_factory=dict)
    
    # Processing stats
    total_listings_fetched: int = 0
    listings_after_filter: int = 0
    listings_enriched: int = 0
    
    # Schema version
    schema_version: str = "2.0.0"
    
    # Error tracking
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class FullRunExport(BaseModel):
    """
    Complete export of a pipeline run.
    Includes all data needed for debugging and analysis.
    """
    metadata: RunMetadata
    
    # The discovered schema
    discovery_schema: DomainDiscoveryOutput
    
    # User preferences
    preferences: PreferenceProfile
    
    # Final ranked results
    top_results: list[RankedListing] = Field(default_factory=list)
    
    # Optional: all candidate listings (for debugging)
    all_candidates: Optional[list[RankedListing]] = Field(
        default=None,
        description="All scored listings, not just top-k"
    )
    
    # Market summary
    market_summary: dict[str, Any] = Field(
        default_factory=dict,
        description="Overall market statistics"
    )

    def to_minimal_export(self) -> dict[str, Any]:
        """Export minimal version without full traces."""
        return {
            "metadata": {
                "run_id": self.metadata.run_id,
                "query": self.metadata.user_query,
                "exported_at": datetime.now().isoformat(),
            },
            "results": [
                {
                    "rank": r.rank,
                    "title": r.listing.title,
                    "price": r.listing.price,
                    "url": r.listing.url,
                    "score": r.scores.total,
                    "seller_questions": [q.question for q in r.enrichment.seller_questions],
                }
                for r in self.top_results
            ],
        }
