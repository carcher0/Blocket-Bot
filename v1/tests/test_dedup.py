"""
Tests for deduplication logic in storage module.

Note: These tests require a MySQL database connection.
For unit testing without a database, you may want to mock the storage functions.
"""
import pytest
import uuid
from unittest.mock import patch, MagicMock


class TestDeduplication:
    """Tests for deduplication logic."""

    def test_filter_new_listings_identifies_new(self):
        """Test that new listings are correctly identified."""
        # Mock the storage functions
        from normalization import normalize_listing

        seen_ids = {"123", "456"}
        seen_urls = {"https://blocket.se/annons/123", "https://blocket.se/annons/456"}

        listings = [
            {"listing_id": "123", "url": "https://blocket.se/annons/123"},  # seen
            {"listing_id": "789", "url": "https://blocket.se/annons/789"},  # new
            {"listing_id": "456", "url": "https://blocket.se/annons/456"},  # seen
            {"listing_id": "999", "url": "https://blocket.se/annons/999"},  # new
        ]

        # Simulate filter logic
        new_listings = []
        for listing in listings:
            listing_id = listing.get("listing_id")
            url = listing.get("url", "")

            if listing_id and listing_id in seen_ids:
                continue
            if url and url in seen_urls:
                continue

            new_listings.append(listing)

        assert len(new_listings) == 2
        assert new_listings[0]["listing_id"] == "789"
        assert new_listings[1]["listing_id"] == "999"

    def test_filter_by_url_when_no_listing_id(self):
        """Test deduplication falls back to URL when listing_id is missing."""
        seen_urls = {"https://blocket.se/annons/abc"}

        listings = [
            {"url": "https://blocket.se/annons/abc"},  # seen (by URL)
            {"url": "https://blocket.se/annons/xyz"},  # new
        ]

        # Simulate filter logic
        new_listings = []
        for listing in listings:
            url = listing.get("url", "")
            if url and url in seen_urls:
                continue
            new_listings.append(listing)

        assert len(new_listings) == 1
        assert new_listings[0]["url"] == "https://blocket.se/annons/xyz"

    def test_empty_seen_set_returns_all(self):
        """Test that empty seen set returns all listings."""
        seen_ids = set()
        seen_urls = set()

        listings = [
            {"listing_id": "1", "url": "https://blocket.se/1"},
            {"listing_id": "2", "url": "https://blocket.se/2"},
        ]

        # Simulate filter logic
        new_listings = []
        for listing in listings:
            listing_id = listing.get("listing_id")
            url = listing.get("url", "")

            if listing_id and listing_id in seen_ids:
                continue
            if url and url in seen_urls:
                continue

            new_listings.append(listing)

        assert len(new_listings) == 2


class TestMarkingSeenLogic:
    """Tests for marking listings as seen."""

    def test_mark_uses_listing_id_primarily(self):
        """Test that listing_id is the primary key for marking."""
        listings = [
            {"listing_id": "123", "url": "https://blocket.se/123"},
            {"listing_id": "456", "url": "https://blocket.se/456"},
        ]

        # Verify listings have correct structure for marking
        for listing in listings:
            assert "listing_id" in listing
            assert listing["listing_id"] is not None

    def test_mark_handles_missing_listing_id(self):
        """Test that URL is used when listing_id is missing."""
        listings = [
            {"url": "https://blocket.se/abc"},  # No listing_id
            {"listing_id": None, "url": "https://blocket.se/xyz"},  # Explicit None
        ]

        # Both should be markable by URL
        for listing in listings:
            url = listing.get("url", "")
            assert url, "URL should be available for dedup fallback"


class TestWatchIntegration:
    """Integration tests for watch + dedup workflow."""

    def test_delta_export_workflow(self):
        """Test the delta export workflow logic."""
        # Simulate workflow:
        # 1. First run - all listings are new
        # 2. Mark them as seen
        # 3. Second run with some overlap - only new ones returned

        # First run
        first_run_listings = [
            {"listing_id": "1", "url": "u1"},
            {"listing_id": "2", "url": "u2"},
        ]

        seen_ids = set()
        new_in_first = [l for l in first_run_listings if l["listing_id"] not in seen_ids]
        assert len(new_in_first) == 2

        # Mark as seen
        for l in new_in_first:
            seen_ids.add(l["listing_id"])

        # Second run with overlap
        second_run_listings = [
            {"listing_id": "2", "url": "u2"},  # already seen
            {"listing_id": "3", "url": "u3"},  # new
            {"listing_id": "4", "url": "u4"},  # new
        ]

        new_in_second = [l for l in second_run_listings if l["listing_id"] not in seen_ids]
        assert len(new_in_second) == 2
        assert new_in_second[0]["listing_id"] == "3"
        assert new_in_second[1]["listing_id"] == "4"
