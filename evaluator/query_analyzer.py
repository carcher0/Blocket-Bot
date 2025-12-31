"""
Query Analyzer: Analyze search queries and determine product family and key attributes.
"""
from typing import Optional
from collections import Counter
import re

from .schemas import (
    QueryAnalysisResult,
    ClusterInfo,
    ProductFamily,
)


# Keywords that indicate phone-related queries
PHONE_KEYWORDS = [
    r"iphone", r"samsung", r"galaxy", r"pixel", r"huawei", r"oneplus",
    r"xiaomi", r"mobiltelefon", r"smartphone", r"telefon", r"mobil",
]

# Keywords that indicate laptop-related queries
LAPTOP_KEYWORDS = [
    r"macbook", r"laptop", r"notebook", r"dator", r"thinkpad",
    r"dell\s*xps", r"surface\s*pro", r"chromebook",
]

# Keywords that indicate accessories (to filter out)
ACCESSORY_KEYWORDS = [
    r"skal", r"case", r"laddare", r"charger", r"kabel", r"cable",
    r"adapter", r"skärmskydd", r"screen\s*protector", r"hörlurar",
    r"airpods", r"earpods", r"hållare", r"mount", r"stativ",
]


def analyze_query(
    query: str,
    probe_listings: Optional[list[dict]] = None,
) -> QueryAnalysisResult:
    """
    Analyze a search query to determine product family and key attributes.
    
    Args:
        query: The search query string
        probe_listings: Optional probe batch of listings for analysis
        
    Returns:
        QueryAnalysisResult with product family, confidence, and any clarifications needed
    """
    query_lower = query.lower()
    
    # Detect product family from query
    family = ProductFamily.UNKNOWN
    confidence = 0.5
    key_attributes = []
    
    # Check for phone keywords
    for pattern in PHONE_KEYWORDS:
        if re.search(pattern, query_lower):
            family = ProductFamily.PHONE
            confidence = 0.9
            key_attributes = ["model_variant", "storage_gb", "condition", "battery_health"]
            break
    
    # Check for laptop keywords
    if family == ProductFamily.UNKNOWN:
        for pattern in LAPTOP_KEYWORDS:
            if re.search(pattern, query_lower):
                family = ProductFamily.LAPTOP
                confidence = 0.85
                key_attributes = ["model_variant", "cpu", "ram_gb", "storage_gb", "condition"]
                break
    
    # Analyze probe listings if available
    clusters: list[ClusterInfo] = []
    is_ambiguous = False
    clarifying_question = None
    clarifying_options: list[str] = []
    
    if probe_listings:
        # Analyze titles for coherence
        titles = [l.get("title", "") or "" for l in probe_listings if l.get("title")]
        
        # Check for accessory contamination
        accessory_count = 0
        main_product_count = 0
        
        for title in titles:
            title_lower = title.lower()
            is_accessory = any(re.search(p, title_lower) for p in ACCESSORY_KEYWORDS)
            if is_accessory:
                accessory_count += 1
            else:
                main_product_count += 1
        
        total = len(titles)
        if total > 0:
            accessory_ratio = accessory_count / total
            
            # If significant accessory contamination, mark as ambiguous
            if 0.15 < accessory_ratio < 0.85:
                is_ambiguous = True
                clarifying_question = "Söker du efter produkten eller tillbehör?"
                clarifying_options = [
                    f"Produkten ({main_product_count} annonser)",
                    f"Tillbehör ({accessory_count} annonser)",
                ]
        
        # Analyze price clusters
        prices = []
        for l in probe_listings:
            price_data = l.get("price", {})
            if isinstance(price_data, dict):
                amount = price_data.get("amount")
                if amount and amount > 0:
                    prices.append(amount)
        
        if prices:
            # Simple clustering: find if there's a clear split
            sorted_prices = sorted(prices)
            median_price = sorted_prices[len(sorted_prices) // 2]
            
            low_prices = [p for p in prices if p < median_price * 0.3]
            high_prices = [p for p in prices if p >= median_price * 0.3]
            
            if low_prices and len(low_prices) >= 3:
                clusters.append(ClusterInfo(
                    label="Billigare produkter/tillbehör",
                    median_price=sorted(low_prices)[len(low_prices) // 2],
                    count=len(low_prices),
                ))
            
            if high_prices:
                clusters.append(ClusterInfo(
                    label="Huvudprodukter",
                    median_price=sorted(high_prices)[len(high_prices) // 2],
                    count=len(high_prices),
                ))
    
    return QueryAnalysisResult(
        query=query,
        product_family=family,
        confidence=confidence,
        key_attributes=key_attributes,
        clusters=clusters,
        is_ambiguous=is_ambiguous,
        clarifying_question=clarifying_question,
        clarifying_options=clarifying_options,
        probe_sample_size=len(probe_listings) if probe_listings else 0,
    )


def should_filter_accessories(listings: list[dict]) -> list[dict]:
    """
    Filter out accessory listings from a search result.
    Returns only main product listings.
    """
    filtered = []
    for listing in listings:
        title = (listing.get("title", "") or "").lower()
        is_accessory = any(re.search(p, title) for p in ACCESSORY_KEYWORDS)
        if not is_accessory:
            filtered.append(listing)
    return filtered


def get_title_coherence(titles: list[str]) -> float:
    """
    Measure how coherent/similar the titles are.
    Returns 0-1 where 1 is highly coherent.
    """
    if len(titles) < 2:
        return 1.0
    
    # Simple approach: count common words
    word_counts: Counter = Counter()
    for title in titles:
        words = set(re.findall(r'\w+', title.lower()))
        for word in words:
            word_counts[word] += 1
    
    # Words that appear in >50% of titles
    threshold = len(titles) * 0.5
    common_words = sum(1 for w, c in word_counts.items() if c >= threshold and len(w) > 2)
    
    # Normalize
    coherence = min(1.0, common_words / 5)  # Expect ~5 common words for good coherence
    return coherence
