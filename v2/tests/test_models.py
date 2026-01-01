"""
Tests for Pydantic models.
"""
import pytest
from datetime import datetime

from v2.models.listing import Listing, NormalizedListing
from v2.models.discovery import (
    AttributeCandidate,
    PreferenceQuestion,
    DomainDiscoveryOutput,
    InferredDomain,
    DEFAULT_GENERIC_SCHEMA,
)
from v2.models.preferences import PreferenceProfile, PreferenceValue
from v2.models.enrichment import EnrichedListing, ExtractedAttribute, RiskFlag
from v2.models.scoring import MarketStats, ScoringBreakdown, ValueScore, PreferenceScore, RiskScore


class TestListingModels:
    """Tests for listing models."""
    
    def test_listing_with_complete_data(self):
        """Test Listing creation with complete data."""
        listing = Listing(
            listing_id="123",
            url="https://blocket.se/annons/123",
            title="iPhone 15 Pro 128GB",
            description="Som ny, inga repor",
            price=12000,
            currency="SEK",
            location="Stockholm",
            shipping_available=True,
        )
        
        assert listing.listing_id == "123"
        assert listing.price == 12000
        assert listing.shipping_available is True
    
    def test_listing_price_parsing_dict(self):
        """Test price parsing from dict format."""
        listing = Listing(
            listing_id="123",
            url="https://blocket.se/annons/123",
            title="Test",
            price={"value": 5000, "currency": "SEK"},
        )
        
        assert listing.price == 5000.0
    
    def test_listing_price_parsing_string(self):
        """Test price parsing from string format."""
        listing = Listing(
            listing_id="123",
            url="https://blocket.se/annons/123",
            title="Test",
            price="7 500 kr",
        )
        
        assert listing.price == 7500.0
    
    def test_normalized_listing_search_text(self):
        """Test that search_text is built correctly."""
        listing = NormalizedListing(
            listing_id="123",
            url="https://blocket.se/annons/123",
            title="iPhone 15",
            description="Som ny skick",
        )
        
        assert "iphone" in listing.search_text
        assert "som ny" in listing.search_text


class TestDiscoveryModels:
    """Tests for discovery models."""
    
    def test_attribute_candidate_validation(self):
        """Test AttributeCandidate field validation."""
        attr = AttributeCandidate(
            name="storage_gb",
            display_name="Lagring",
            type="number",
            importance_weight=0.8,
        )
        
        assert attr.name == "storage_gb"
        assert 0 <= attr.importance_weight <= 1
    
    def test_attribute_candidate_weight_bounds(self):
        """Test that importance_weight is bounded."""
        with pytest.raises(ValueError):
            AttributeCandidate(
                name="test",
                display_name="Test",
                type="text",
                importance_weight=1.5,  # Should fail
            )
    
    def test_domain_discovery_output(self):
        """Test DomainDiscoveryOutput creation."""
        output = DomainDiscoveryOutput(
            inferred_domain=InferredDomain(
                domain_label="smartphone",
                confidence=0.95,
            ),
            attribute_candidates=[
                AttributeCandidate(
                    name="storage_gb",
                    display_name="Lagring",
                    type="number",
                    importance_weight=0.8,
                )
            ],
            sample_size=30,
        )
        
        assert output.inferred_domain.domain_label == "smartphone"
        assert len(output.attribute_candidates) == 1
    
    def test_default_generic_schema_exists(self):
        """Test that default generic schema is valid."""
        assert DEFAULT_GENERIC_SCHEMA is not None
        assert DEFAULT_GENERIC_SCHEMA.inferred_domain.domain_label == "generic"
        assert len(DEFAULT_GENERIC_SCHEMA.attribute_candidates) > 0


class TestPreferenceModels:
    """Tests for preference models."""
    
    def test_preference_profile_creation(self):
        """Test PreferenceProfile creation."""
        profile = PreferenceProfile(
            user_query="iPhone 15",
            max_price=15000,
            require_shipping=True,
        )
        
        assert profile.user_query == "iPhone 15"
        assert profile.max_price == 15000
    
    def test_preference_value_types(self):
        """Test PreferenceValue constraint types."""
        pref = PreferenceValue(
            attribute="condition",
            value=["ny", "som ny"],
            constraint_type="in",
        )
        
        assert pref.constraint_type == "in"
        assert isinstance(pref.value, list)


class TestEnrichmentModels:
    """Tests for enrichment models."""
    
    def test_extracted_attribute_confidence_bounds(self):
        """Test confidence is bounded 0-1."""
        attr = ExtractedAttribute(
            name="storage_gb",
            value=128,
            confidence=0.95,
        )
        
        assert 0 <= attr.confidence <= 1
        
        with pytest.raises(ValueError):
            ExtractedAttribute(
                name="test",
                value="val",
                confidence=1.5,
            )
    
    def test_enriched_listing_helpers(self):
        """Test EnrichedListing helper methods."""
        enriched = EnrichedListing(
            listing_id="123",
            extracted_attributes={
                "storage_gb": ExtractedAttribute(
                    name="storage_gb",
                    value=256,
                    confidence=0.9,
                )
            },
            missing_fields=["battery_health"],
        )
        
        assert enriched.get_attribute_value("storage_gb") == 256
        assert enriched.get_attribute_value("missing", default=None) is None
        assert enriched.get_attribute_confidence("storage_gb") == 0.9


class TestScoringModels:
    """Tests for scoring models."""
    
    def test_market_stats_creation(self):
        """Test MarketStats creation."""
        stats = MarketStats(
            median=10000,
            iqr=2000,
            q1=9000,
            q3=11000,
            min_price=7000,
            max_price=15000,
            n=25,
        )
        
        assert stats.median == 10000
        assert stats.is_sufficient is True
    
    def test_scoring_breakdown_bounds(self):
        """Test ScoringBreakdown score bounds."""
        breakdown = ScoringBreakdown(
            total=75.5,
            value_score=ValueScore(
                score=80,
                asking_price=9000,
                expected_price=10000,
                deal_delta=1000,
                deal_delta_percent=10,
                explanation="Bra pris",
            ),
            preference_score=PreferenceScore(
                score=70,
                explanation="Bra match",
            ),
            risk_score=RiskScore(
                score=85,
                explanation="Låg risk",
            ),
            summary_explanation="Bra köp",
        )
        
        assert 0 <= breakdown.total <= 100
        assert 0 <= breakdown.value_score.score <= 100
