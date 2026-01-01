"""
Listing models - raw and normalized listing representations.
"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class Listing(BaseModel):
    """Raw listing as received from Blocket API."""
    listing_id: str
    url: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: str = "SEK"
    location: Optional[str] = None
    published_at: Optional[datetime] = None
    shipping_available: Optional[bool] = None
    images: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)
    fetched_at: datetime = Field(default_factory=datetime.now)

    @field_validator("price", mode="before")
    @classmethod
    def parse_price(cls, v: Any) -> Optional[float]:
        """Parse price from various formats."""
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            # Remove common formatting: "7 500 kr", "7,500 SEK"
            cleaned = v.replace(" ", "").replace(",", "").replace("kr", "").replace("SEK", "")
            try:
                return float(cleaned)
            except ValueError:
                return None
        if isinstance(v, dict):
            return float(v.get("value") or v.get("amount") or 0)
        return None


class NormalizedListing(BaseModel):
    """
    Normalized listing with consistent field names.
    This is the internal representation used throughout the pipeline.
    """
    listing_id: str
    url: str
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    location: Optional[str] = None
    published_at: Optional[datetime] = None
    shipping_available: Optional[bool] = None
    image_count: int = 0
    fetched_at: datetime = Field(default_factory=datetime.now)
    
    # Combined searchable text for filtering
    search_text: str = ""
    
    # Reference to original data
    raw: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Build search text after initialization."""
        parts = [self.title or ""]
        if self.description:
            parts.append(self.description)
        self.search_text = " ".join(parts).lower()
