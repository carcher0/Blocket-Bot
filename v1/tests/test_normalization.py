"""
Tests for the normalization module.
"""
import pytest
from datetime import datetime, timezone

from normalization import (
    normalize_listing,
    normalize_listings,
    create_export,
    Listing,
    Filters,
    Preferences,
    Export,
)


class TestNormalizeListing:
    """Tests for normalize_listing function."""

    def test_complete_data(self):
        """Test normalization with complete data."""
        raw = {
            "id": "12345678",
            "url": "https://blocket.se/annons/12345678",
            "title": "iPhone 15 Pro 256GB",
            "price": {"value": 12500, "currency": "SEK"},
            "location": {"name": "Stockholm"},
            "published": "2024-12-30T10:00:00+01:00",
            "shipping": True,
        }

        result = normalize_listing(raw)

        assert result.listing_id == "12345678"
        assert result.url == "https://blocket.se/annons/12345678"
        assert result.title == "iPhone 15 Pro 256GB"
        assert result.price.amount == 12500
        assert result.price.currency == "SEK"
        assert result.location == "Stockholm"
        assert result.published_at == "2024-12-30T10:00:00+01:00"
        assert result.shipping_available is True
        assert result.fetched_at is not None
        assert result.raw == raw

    def test_missing_fields_returns_null(self):
        """Test that missing fields return null values."""
        raw = {}

        result = normalize_listing(raw)

        assert result.listing_id is None
        assert result.title is None
        assert result.price.amount is None
        assert result.price.currency is None
        assert result.location is None
        assert result.published_at is None
        assert result.shipping_available is None
        assert result.fetched_at is not None  # Always set

    def test_alternative_field_names(self):
        """Test extraction from alternative field names."""
        raw = {
            "ad_id": "99999",
            "subject": "MacBook Pro M3",
            "area": "Göteborg",
            "created_at": "2024-12-29T15:30:00Z",
            "can_be_shipped": True,
        }

        result = normalize_listing(raw)

        assert result.listing_id == "99999"
        assert result.title == "MacBook Pro M3"
        assert result.location == "Göteborg"
        assert result.published_at == "2024-12-29T15:30:00Z"
        assert result.shipping_available is True

    def test_price_as_number(self):
        """Test price extraction when price is a simple number."""
        raw = {
            "id": "123",
            "price": 5000,
        }

        result = normalize_listing(raw)

        assert result.price.amount == 5000.0
        assert result.price.currency == "SEK"

    def test_price_as_string(self):
        """Test price extraction from string format."""
        raw = {
            "id": "123",
            "price": "7 500 kr",
        }

        result = normalize_listing(raw)

        assert result.price.amount == 7500.0
        assert result.price.currency == "SEK"

    def test_generated_url_from_id(self):
        """Test URL generation when URL is missing but ID exists."""
        raw = {
            "id": "12345678",
        }

        result = normalize_listing(raw)

        assert result.listing_id == "12345678"
        assert "12345678" in result.url


class TestNormalizeListings:
    """Tests for normalize_listings function."""

    def test_empty_list(self):
        """Test normalization of empty list."""
        result = normalize_listings([])
        assert result == []

    def test_multiple_items(self):
        """Test normalization of multiple items."""
        raw_items = [
            {"id": "1", "title": "Item 1"},
            {"id": "2", "title": "Item 2"},
            {"id": "3", "title": "Item 3"},
        ]

        result = normalize_listings(raw_items)

        assert len(result) == 3
        assert result[0].listing_id == "1"
        assert result[1].listing_id == "2"
        assert result[2].listing_id == "3"


class TestCreateExport:
    """Tests for create_export function."""

    def test_creates_valid_export(self):
        """Test that create_export produces a valid Export object."""
        listings = [
            normalize_listing({"id": "1", "title": "Test"}),
        ]
        filters = Filters(locations=["stockholm"], sort_order="price_asc")
        preferences = Preferences(no_cracks=True, min_battery_health=80)

        result = create_export(
            listings=listings,
            query="iPhone",
            watch_id="test-watch-123",
            filters=filters,
            preferences=preferences,
            mode="delta",
        )

        assert isinstance(result, Export)
        assert result.metadata.query == "iPhone"
        assert result.metadata.watch_id == "test-watch-123"
        assert result.metadata.mode == "delta"
        assert result.metadata.filters.locations == ["stockholm"]
        assert result.metadata.preferences.no_cracks is True
        assert len(result.listings) == 1

    def test_export_serializable(self):
        """Test that export can be serialized to JSON."""
        import json

        listings = [normalize_listing({"id": "1", "title": "Test"})]
        result = create_export(listings=listings, query="test")

        # Should not raise
        json_str = json.dumps(result.model_dump())
        assert json_str is not None

        # Can be parsed back
        parsed = json.loads(json_str)
        assert "metadata" in parsed
        assert "listings" in parsed
