"""
Tests for candidate filtering.
"""
import pytest

from v2.models.listing import NormalizedListing
from v2.models.preferences import PreferenceProfile
from v2.pipeline.filter import CandidateFilter


class TestCandidateFilter:
    """Tests for CandidateFilter."""
    
    @pytest.fixture
    def sample_listings(self) -> list[NormalizedListing]:
        """Create sample listings for testing."""
        return [
            NormalizedListing(
                listing_id="1",
                url="https://blocket.se/1",
                title="iPhone 15 Pro 256GB",
                price=12000,
                location="Stockholm",
            ),
            NormalizedListing(
                listing_id="2",
                url="https://blocket.se/2",
                title="iPhone 15 128GB",
                price=9000,
                location="Göteborg",
            ),
            NormalizedListing(
                listing_id="3",
                url="https://blocket.se/3",
                title="iPhone skal rosa",
                price=100,
                location="Stockholm",
            ),
            NormalizedListing(
                listing_id="4",
                url="https://blocket.se/4",
                title="iPhone 15 Pro Max 512GB",
                price=18000,
                location="Malmö",
            ),
            NormalizedListing(
                listing_id="5",
                url="https://blocket.se/5",
                title="Samsung Galaxy S24",
                price=11000,
                location="Stockholm",
            ),
        ]
    
    def test_filter_reduces_count(self, sample_listings):
        """Test that filter reduces listing count."""
        filter_obj = CandidateFilter(max_candidates=3)
        
        prefs = PreferenceProfile(user_query="iPhone 15")
        result = filter_obj.filter(sample_listings, prefs)
        
        assert len(result) <= 3
    
    def test_max_price_constraint(self, sample_listings):
        """Test that max_price filters correctly."""
        filter_obj = CandidateFilter(max_candidates=10)
        
        prefs = PreferenceProfile(
            user_query="iPhone",
            max_price=10000,
        )
        result = filter_obj.filter(sample_listings, prefs)
        
        # All results should be <= max_price
        for listing in result:
            if listing.price:
                assert listing.price <= 10000
    
    def test_min_price_constraint(self, sample_listings):
        """Test that min_price filters correctly."""
        filter_obj = CandidateFilter(max_candidates=10)
        
        prefs = PreferenceProfile(
            user_query="iPhone",
            min_price=5000,
        )
        result = filter_obj.filter(sample_listings, prefs)
        
        # All results should be >= min_price
        for listing in result:
            if listing.price:
                assert listing.price >= 5000
    
    def test_location_constraint(self, sample_listings):
        """Test that location filters correctly."""
        filter_obj = CandidateFilter(max_candidates=10)
        
        prefs = PreferenceProfile(
            user_query="iPhone",
            locations=["Stockholm"],
        )
        result = filter_obj.filter(sample_listings, prefs)
        
        # All results should be in Stockholm
        for listing in result:
            if listing.location:
                assert "Stockholm" in listing.location
    
    def test_relevance_scoring_orders_correctly(self, sample_listings):
        """Test that more relevant items score higher."""
        filter_obj = CandidateFilter(max_candidates=10)
        
        prefs = PreferenceProfile(user_query="iPhone 15 Pro")
        result = filter_obj.filter(sample_listings, prefs)
        
        # The first result should contain the query terms
        if result:
            first = result[0]
            assert "iphone" in first.title.lower()
    
    def test_empty_listings_returns_empty(self):
        """Test that empty input returns empty output."""
        filter_obj = CandidateFilter()
        
        prefs = PreferenceProfile(user_query="test")
        result = filter_obj.filter([], prefs)
        
        assert result == []
    
    def test_shipping_constraint(self):
        """Test that require_shipping filters correctly."""
        listings = [
            NormalizedListing(
                listing_id="1",
                url="https://blocket.se/1",
                title="Test 1",
                price=1000,
                shipping_available=True,
            ),
            NormalizedListing(
                listing_id="2",
                url="https://blocket.se/2",
                title="Test 2",
                price=1000,
                shipping_available=False,
            ),
            NormalizedListing(
                listing_id="3",
                url="https://blocket.se/3",
                title="Test 3",
                price=1000,
                shipping_available=None,  # Unknown
            ),
        ]
        
        filter_obj = CandidateFilter(max_candidates=10)
        
        prefs = PreferenceProfile(
            user_query="Test",
            require_shipping=True,
        )
        result = filter_obj.filter(listings, prefs)
        
        # Only the one with shipping should pass
        assert len(result) == 1
        assert result[0].listing_id == "1"
