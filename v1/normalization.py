"""
Normalization module for converting BlocketAPI responses to a standardized export schema.
"""
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field


class Price(BaseModel):
    """Price information for a listing."""
    amount: Optional[float] = None
    currency: Optional[str] = None


class Listing(BaseModel):
    """Normalized listing from Blocket."""
    listing_id: Optional[str] = None
    url: str
    title: Optional[str] = None
    price: Price = Field(default_factory=Price)
    location: Optional[str] = None
    published_at: Optional[str] = None
    shipping_available: Optional[bool] = None
    fetched_at: str
    raw: dict[str, Any] = Field(default_factory=dict)


class Filters(BaseModel):
    """Search filters applied."""
    locations: list[str] = Field(default_factory=list)
    category: Optional[str] = None
    sort_order: Optional[str] = None


class Preferences(BaseModel):
    """User preferences for evaluation (not used in search yet)."""
    condition: Optional[str] = None  # ny, som_ny, bra, ok, defekt
    no_cracks: bool = False
    min_battery_health: Optional[int] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    location_requirements: Optional[str] = None
    shipping_required: bool = False
    other_requirements: Optional[str] = None


class ExportMetadata(BaseModel):
    """Metadata for the export file."""
    exported_at: str
    query: Optional[str] = None
    watch_id: Optional[str] = None
    filters: Filters = Field(default_factory=Filters)
    preferences: Preferences = Field(default_factory=Preferences)
    mode: str = "full"  # "full" or "delta"


class Export(BaseModel):
    """Complete export object."""
    metadata: ExportMetadata
    listings: list[Listing] = Field(default_factory=list)


def normalize_listing(raw_item: dict[str, Any]) -> Listing:
    """
    Convert a raw API response item to a normalized Listing.

    Safely extracts fields with null fallbacks for missing data.
    Based on BlocketAPI actual response format.
    """
    from datetime import datetime, timezone
    
    fetched_at = datetime.now(timezone.utc).isoformat()

    # Extract listing ID - BlocketAPI uses 'ad_id' or 'id'
    listing_id = None
    for key in ["ad_id", "id", "listing_id", "adId"]:
        if key in raw_item and raw_item[key] is not None:
            listing_id = str(raw_item[key])
            break

    # Extract URL - BlocketAPI uses 'canonical_url' or 'share_url'
    url = raw_item.get("canonical_url") or raw_item.get("share_url") or raw_item.get("url") or ""
    if not url and listing_id:
        url = f"https://www.blocket.se/annons/{listing_id}"

    # Extract title - BlocketAPI uses 'heading' or 'subject'
    title = raw_item.get("heading") or raw_item.get("title") or raw_item.get("subject") or raw_item.get("name")

    # Extract price - BlocketAPI uses nested structure with 'value' and 'currency'
    price_data = Price()
    if "price" in raw_item:
        price_val = raw_item["price"]
        if isinstance(price_val, dict):
            price_data.amount = price_val.get("value") or price_val.get("amount")
            price_data.currency = price_val.get("currency", "SEK")
        elif isinstance(price_val, (int, float)):
            price_data.amount = float(price_val)
            price_data.currency = "SEK"
        elif isinstance(price_val, str):
            try:
                cleaned = price_val.replace(" ", "").replace("kr", "").replace("SEK", "").replace(",", "")
                price_data.amount = float(cleaned)
                price_data.currency = "SEK"
            except ValueError:
                pass

    # Extract location - BlocketAPI returns 'location' as a string
    location = None
    if "location" in raw_item:
        loc = raw_item["location"]
        if isinstance(loc, str):
            location = loc
        elif isinstance(loc, dict):
            location = loc.get("name") or loc.get("city") or loc.get("region")
    elif "location_name" in raw_item:
        location = raw_item["location_name"]
    elif "municipality" in raw_item:
        location = raw_item["municipality"]
    elif "region" in raw_item:
        location = raw_item["region"]

    # Extract published date - BlocketAPI uses 'timestamp' (milliseconds) or 'list_time'
    published_at = None
    # First try timestamp (milliseconds since epoch)
    if "timestamp" in raw_item and raw_item["timestamp"]:
        try:
            ts_ms = raw_item["timestamp"]
            if isinstance(ts_ms, (int, float)):
                dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
                published_at = dt.isoformat()
        except (ValueError, OSError):
            pass
    # Fallback to other date fields
    if not published_at:
        for key in ["list_time", "published", "published_at", "created", "created_at", "date"]:
            if key in raw_item and raw_item[key]:
                val = raw_item[key]
                if isinstance(val, str):
                    published_at = val
                elif hasattr(val, "isoformat"):
                    published_at = val.isoformat()
                break

    # Extract shipping info - BlocketAPI uses 'shipping' or 'can_be_shipped'
    shipping_available = None
    if "shipping" in raw_item:
        ship = raw_item["shipping"]
        if isinstance(ship, bool):
            shipping_available = ship
        elif isinstance(ship, dict):
            shipping_available = ship.get("available", False) or ship.get("enabled", False)
    elif "can_be_shipped" in raw_item:
        shipping_available = bool(raw_item["can_be_shipped"])

    return Listing(
        listing_id=listing_id,
        url=url,
        title=title,
        price=price_data,
        location=location,
        published_at=published_at,
        shipping_available=shipping_available,
        fetched_at=fetched_at,
        raw=raw_item,
    )


def create_export(
    listings: list[Listing],
    query: Optional[str] = None,
    watch_id: Optional[str] = None,
    filters: Optional[Filters] = None,
    preferences: Optional[Preferences] = None,
    mode: str = "full",
) -> Export:
    """
    Create a complete export object with metadata.
    """
    metadata = ExportMetadata(
        exported_at=datetime.now(timezone.utc).isoformat(),
        query=query,
        watch_id=watch_id,
        filters=filters or Filters(),
        preferences=preferences or Preferences(),
        mode=mode,
    )

    return Export(metadata=metadata, listings=listings)


def normalize_listings(raw_items: list[dict[str, Any]]) -> list[Listing]:
    """
    Normalize a list of raw API response items.
    """
    return [normalize_listing(item) for item in raw_items]
