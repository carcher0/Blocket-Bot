"""
Tests for scoring determinism.
Same input must always produce same output.
"""
import pytest

from v2.models.listing import NormalizedListing
from v2.models.enrichment import EnrichedListing, ExtractedAttribute
from v2.models.preferences import PreferenceProfile
from v2.models.scoring import MarketStats
from v2.pipeline.scoring import ScoringEngine


class TestScoringDeterminism:
    """Test that scoring is deterministic."""
    
    @pytest.fixture
    def sample_listing(self) -> NormalizedListing:
        """Create a sample listing for testing."""
        return NormalizedListing(
            listing_id="test123",
            url="https://blocket.se/annons/test123",
            title="iPhone 15 Pro 256GB",
            description="Som ny, inga repor",
            price=12000,
            location="Stockholm",
        )
    
    @pytest.fixture
    def sample_enrichment(self) -> EnrichedListing:
        """Create sample enrichment data."""
        return EnrichedListing(
            listing_id="test123",
            extracted_attributes={
                "storage_gb": ExtractedAttribute(
                    name="storage_gb",
                    value=256,
                    confidence=0.95,
                ),
                "condition": ExtractedAttribute(
                    name="condition",
                    value="som ny",
                    confidence=0.9,
                ),
            },
            extraction_confidence=0.9,
            missing_fields=[],
            risk_flags=[],
        )
    
    @pytest.fixture
    def sample_market_stats(self) -> MarketStats:
        """Create sample market stats."""
        return MarketStats(
            median=13000,
            iqr=2000,
            q1=12000,
            q3=14000,
            min_price=9000,
            max_price=18000,
            n=20,
            is_sufficient=True,
        )
    
    @pytest.fixture
    def sample_preferences(self) -> PreferenceProfile:
        """Create sample preferences."""
        return PreferenceProfile(
            user_query="iPhone 15 Pro",
            max_price=15000,
        )
    
    def test_same_input_same_score(
        self,
        sample_listing,
        sample_enrichment,
        sample_market_stats,
        sample_preferences,
    ):
        """Test that identical inputs produce identical scores."""
        scorer = ScoringEngine()
        
        # Score the same listing multiple times
        scores = []
        for _ in range(5):
            result = scorer.score(
                sample_listing,
                sample_enrichment,
                sample_market_stats,
                sample_preferences,
            )
            scores.append(result.total)
        
        # All scores should be identical
        assert all(s == scores[0] for s in scores)
    
    def test_value_score_calculation(
        self,
        sample_listing,
        sample_enrichment,
        sample_market_stats,
        sample_preferences,
    ):
        """Test value score calculation logic."""
        scorer = ScoringEngine()
        
        result = scorer.score(
            sample_listing,
            sample_enrichment,
            sample_market_stats,
            sample_preferences,
        )
        
        # Asking 12000, median 13000 = 1000 below market = good deal
        assert result.value_score.deal_delta > 0
        assert result.value_score.score > 50  # Better than average
    
    def test_risk_score_with_no_flags(
        self,
        sample_listing,
        sample_enrichment,
        sample_market_stats,
        sample_preferences,
    ):
        """Test risk score when no flags present."""
        scorer = ScoringEngine()
        
        result = scorer.score(
            sample_listing,
            sample_enrichment,
            sample_market_stats,
            sample_preferences,
        )
        
        # No risk flags = perfect risk score
        assert result.risk_score.score == 100.0
    
    def test_weights_sum_to_one(self):
        """Test that default weights sum to 1."""
        scorer = ScoringEngine()
        
        total_weight = (
            scorer.value_weight
            + scorer.preference_weight
            + scorer.risk_weight
        )
        
        assert total_weight == 1.0
    
    def test_custom_weights(
        self,
        sample_listing,
        sample_enrichment,
        sample_market_stats,
        sample_preferences,
    ):
        """Test scoring with custom weights."""
        scorer1 = ScoringEngine(
            value_weight=0.7,
            preference_weight=0.2,
            risk_weight=0.1,
        )
        
        scorer2 = ScoringEngine(
            value_weight=0.3,
            preference_weight=0.5,
            risk_weight=0.2,
        )
        
        result1 = scorer1.score(
            sample_listing,
            sample_enrichment,
            sample_market_stats,
            sample_preferences,
        )
        
        result2 = scorer2.score(
            sample_listing,
            sample_enrichment,
            sample_market_stats,
            sample_preferences,
        )
        
        # Weights should be reflected
        assert result1.value_weight == 0.7
        assert result2.value_weight == 0.3
        
        # Different weights = different total (usually)
        # Note: might be same if component scores happen to average out


class TestScoringEdgeCases:
    """Test edge cases in scoring."""
    
    def test_missing_price(self):
        """Test scoring when listing has no price."""
        scorer = ScoringEngine()
        
        listing = NormalizedListing(
            listing_id="test",
            url="https://blocket.se/annons/test",
            title="Test",
            price=None,  # Missing price
        )
        
        enrichment = EnrichedListing(listing_id="test")
        market = MarketStats(
            median=10000, iqr=2000, q1=9000, q3=11000,
            min_price=5000, max_price=15000, n=10,
        )
        prefs = PreferenceProfile(user_query="test")
        
        result = scorer.score(listing, enrichment, market, prefs)
        
        # Should still return a valid score
        assert 0 <= result.total <= 100
        # Value score should be neutral (50)
        assert result.value_score.score == 50.0
    
    def test_insufficient_comps(self):
        """Test scoring with insufficient market data."""
        scorer = ScoringEngine()
        
        listing = NormalizedListing(
            listing_id="test",
            url="https://blocket.se/annons/test",
            title="Test",
            price=10000,
        )
        
        enrichment = EnrichedListing(listing_id="test")
        market = MarketStats(
            median=10000, iqr=0, q1=10000, q3=10000,
            min_price=10000, max_price=10000, n=1,
            is_sufficient=False,  # Not enough comps
        )
        prefs = PreferenceProfile(user_query="test")
        
        result = scorer.score(listing, enrichment, market, prefs)
        
        # Value score should be neutral when comps insufficient
        assert result.value_score.score == 50.0
