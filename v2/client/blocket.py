"""
Blocket API client with retry logic and normalization.
"""
import logging
from datetime import datetime
from typing import Any, Optional

from blocket_api import BlocketAPI, Location, SortOrder
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import requests

from ..models.listing import Listing, NormalizedListing


logger = logging.getLogger(__name__)


class BlocketClient:
    """
    Wrapper around BlocketAPI with retry logic and structured output.
    Returns normalized Listing models instead of raw dicts.
    """

    # Location mapping
    LOCATIONS = {
        "blekinge": Location.BLEKINGE,
        "dalarna": Location.DALARNA,
        "gotland": Location.GOTLAND,
        "gavleborg": Location.GAVLEBORG,
        "halland": Location.HALLAND,
        "jamtland": Location.JAMTLAND,
        "jonkoping": Location.JONKOPING,
        "kalmar": Location.KALMAR,
        "kronoberg": Location.KRONOBERG,
        "norrbotten": Location.NORRBOTTEN,
        "skane": Location.SKANE,
        "stockholm": Location.STOCKHOLM,
        "sodermanland": Location.SODERMANLAND,
        "uppsala": Location.UPPSALA,
        "varmland": Location.VARMLAND,
        "vasterbotten": Location.VASTERBOTTEN,
        "vasternorrland": Location.VASTERNORRLAND,
        "vastmanland": Location.VASTMANLAND,
        "vastra_gotaland": Location.VASTRA_GOTALAND,
        "orebro": Location.OREBRO,
        "ostergotland": Location.OSTERGOTLAND,
    }

    # Sort order mapping
    SORT_ORDERS = {
        "relevance": SortOrder.RELEVANCE,
        "price_asc": SortOrder.PRICE_ASC,
        "price_desc": SortOrder.PRICE_DESC,
        "published_desc": SortOrder.PUBLISHED_DESC,
        "published_asc": SortOrder.PUBLISHED_ASC,
    }

    def __init__(self):
        self.api = BlocketAPI()
        logger.info("BlocketClient v2 initialized")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry attempt {retry_state.attempt_number}"
        ),
    )
    def _search_page(self, query: str, page: int = 1, **kwargs) -> dict[str, Any]:
        """Fetch a single page of search results."""
        return self.api.search(query, page=page, **kwargs)

    def search(
        self,
        query: str,
        locations: Optional[list[str]] = None,
        sort_order: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> list[NormalizedListing]:
        """
        Search Blocket and return normalized listings.

        Args:
            query: Search term
            locations: List of location keys
            sort_order: Sort order key
            max_pages: Maximum pages to fetch (None = all)

        Returns:
            List of NormalizedListing objects
        """
        logger.info(f"Searching for: {query}")

        # Build kwargs
        kwargs = {}

        if locations:
            location_enums = [
                self.LOCATIONS[loc]
                for loc in locations
                if loc in self.LOCATIONS
            ]
            if location_enums:
                kwargs["locations"] = location_enums

        if sort_order and sort_order in self.SORT_ORDERS:
            kwargs["sort_order"] = self.SORT_ORDERS[sort_order]

        try:
            all_listings: list[NormalizedListing] = []
            page = 1

            while max_pages is None or page <= max_pages:
                logger.info(f"Fetching page {page}...")
                result = self._search_page(query, page=page, **kwargs)

                # Extract listings from response
                if isinstance(result, dict):
                    listings = result.get("docs", [])
                    is_end = result.get("metadata", {}).get("is_end_of_paging", True)
                else:
                    listings = []
                    is_end = True

                # Normalize each listing
                for raw in listings:
                    normalized = self._normalize_raw_listing(raw)
                    if normalized:
                        all_listings.append(normalized)

                if is_end or not listings:
                    logger.info(f"Reached end at page {page}")
                    break

                page += 1

            logger.info(f"Search completed: {len(all_listings)} listings")
            return all_listings

        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def _normalize_raw_listing(self, raw: Any) -> Optional[NormalizedListing]:
        """Normalize a raw listing dict to NormalizedListing model."""
        try:
            # Handle different raw formats
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump()
            elif hasattr(raw, "__dict__"):
                raw = vars(raw)
            elif not isinstance(raw, dict):
                return None

            # Extract fields with fallbacks
            listing_id = str(
                raw.get("id")
                or raw.get("ad_id")
                or raw.get("listing_id")
                or ""
            )

            if not listing_id:
                return None

            url = raw.get("share_url") or raw.get("url")
            if not url:
                # Construct proper Blocket URL
                url = f"https://www.blocket.se/annons/{listing_id}"
            
            # Title: Blocket API uses 'subject' field
            title = raw.get("subject") or raw.get("title") or raw.get("heading") or ""
            
            # Price extraction
            price = None
            price_data = raw.get("price")
            if isinstance(price_data, dict):
                price = float(price_data.get("value") or price_data.get("amount") or 0)
            elif isinstance(price_data, (int, float)):
                price = float(price_data)
            elif isinstance(price_data, str):
                try:
                    cleaned = price_data.replace(" ", "").replace(",", "").replace("kr", "").replace("SEK", "")
                    price = float(cleaned)
                except ValueError:
                    pass

            # Location extraction
            location = None
            loc_data = raw.get("location")
            if isinstance(loc_data, dict):
                location = loc_data.get("name") or loc_data.get("city")
            elif isinstance(loc_data, str):
                location = loc_data
            else:
                location = raw.get("area")

            # Published date
            published_at = None
            pub_str = raw.get("published") or raw.get("created_at") or raw.get("published_at")
            if pub_str:
                try:
                    published_at = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # Shipping
            shipping = raw.get("shipping") or raw.get("can_be_shipped")
            shipping_available = bool(shipping) if shipping is not None else None

            # Images
            images = raw.get("images") or raw.get("image_urls") or []
            if isinstance(images, list):
                image_count = len(images)
            else:
                image_count = 1 if images else 0

            # Description - try multiple fields
            description = (
                raw.get("body") 
                or raw.get("description") 
                or raw.get("text")
                or raw.get("content")
                or None
            )

            return NormalizedListing(
                listing_id=listing_id,
                url=url,
                title=title,
                description=description,
                price=price,
                location=location,
                published_at=published_at,
                shipping_available=shipping_available,
                image_count=image_count,
                fetched_at=datetime.now(),
                raw=raw,
            )

        except Exception as e:
            logger.warning(f"Failed to normalize listing: {e}")
            return None

    def get_location_options(self) -> list[str]:
        """Get available location options."""
        return list(self.LOCATIONS.keys())

    def get_sort_options(self) -> list[str]:
        """Get available sort order options."""
        return list(self.SORT_ORDERS.keys())
