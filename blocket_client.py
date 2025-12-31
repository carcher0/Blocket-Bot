"""
BlocketAPI wrapper with retry/backoff and structured logging.
"""
import json
import logging
from datetime import datetime
from typing import Any, Optional

from blocket_api import BlocketAPI, Category, Location, SortOrder
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests


# Configure structured JSON logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        return json.dumps(log_obj)


logger = logging.getLogger("blocket_client")
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)


class BlocketClient:
    """Wrapper around BlocketAPI with retry logic and structured logging."""

    # Available locations from blocket-api
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

    # Available sort orders
    SORT_ORDERS = {
        "relevance": SortOrder.RELEVANCE,
        "price_asc": SortOrder.PRICE_ASC,
        "price_desc": SortOrder.PRICE_DESC,
        "published_desc": SortOrder.PUBLISHED_DESC,
        "published_asc": SortOrder.PUBLISHED_ASC,
    }

    def __init__(self):
        self.api = BlocketAPI()
        logger.info("BlocketClient initialized")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        before_sleep=lambda retry_state: logger.warning(
            f"Retry attempt {retry_state.attempt_number} after error",
            extra={"attempt": retry_state.attempt_number}
        )
    )
    def _search_page(
        self,
        query: str,
        page: int = 1,
        **kwargs
    ) -> dict[str, Any]:
        """Fetch a single page of search results."""
        return self.api.search(query, page=page, **kwargs)

    def search(
        self,
        query: str,
        locations: Optional[list[str]] = None,
        category: Optional[str] = None,
        sort_order: Optional[str] = None,
        max_pages: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Search Blocket for listings matching the query.
        Fetches ALL pages by default (until is_end_of_paging is True).

        Args:
            query: Search term (e.g., "iPhone 15")
            locations: List of location keys (e.g., ["stockholm", "uppsala"])
            category: Category key (optional)
            sort_order: Sort order key (e.g., "price_asc")
            max_pages: Maximum pages to fetch (None = unlimited, fetches all)

        Returns:
            List of raw listing dictionaries from the API (all data preserved)
        """
        logger.info(
            f"Searching for: {query}",
            extra={"query": query, "locations": locations, "sort_order": sort_order, "max_pages": max_pages or "unlimited"}
        )

        # Build kwargs for the API call
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

        # Note: Category support depends on BlocketAPI implementation
        if category:
            try:
                kwargs["category"] = Category[category.upper()]
            except (KeyError, AttributeError):
                logger.warning(f"Unknown category: {category}")

        try:
            all_listings = []
            page = 1
            
            while max_pages is None or page <= max_pages:
                logger.info(f"Fetching page {page}...", extra={"page": page})
                result = self._search_page(query, page=page, **kwargs)
                
                # Extract listings from response
                if isinstance(result, dict):
                    listings = result.get("docs", [])
                    is_end = result.get("metadata", {}).get("is_end_of_paging", True)
                else:
                    listings = []
                    is_end = True
                
                # Convert to list of dicts if needed
                for item in listings:
                    if isinstance(item, dict):
                        all_listings.append(item)
                    elif hasattr(item, "model_dump"):
                        all_listings.append(item.model_dump())
                    elif hasattr(item, "__dict__"):
                        all_listings.append(vars(item))
                    else:
                        all_listings.append({"raw": str(item)})
                
                # Check if we've reached the end
                if is_end or not listings:
                    logger.info(f"Reached end of results at page {page}")
                    break
                    
                page += 1

            logger.info(
                f"Search completed",
                extra={"query": query, "result_count": len(all_listings), "pages_fetched": page}
            )
            return all_listings

        except Exception as e:
            logger.error(
                f"Search failed: {str(e)}",
                extra={"query": query, "error": str(e)}
            )
            raise

    def get_location_options(self) -> list[str]:
        """Get available location options."""
        return list(self.LOCATIONS.keys())

    def get_sort_options(self) -> list[str]:
        """Get available sort order options."""
        return list(self.SORT_ORDERS.keys())
