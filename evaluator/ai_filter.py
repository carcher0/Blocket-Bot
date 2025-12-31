"""
AI Filter module: Filter listings for relevance using GPT-5.2.
Critical first step in evaluation - removes irrelevant results before scoring.
"""
import json
import re
from typing import Optional
from dataclasses import dataclass

from .llm_client import LLMClient


@dataclass
class QueryUnderstanding:
    """Parsed understanding of user's search query."""
    product_type: str  # "smartphone", "laptop", etc.
    brand: Optional[str]
    model_line: Optional[str]  # "iPhone 15", "Galaxy S24"
    model_variant: Optional[str]  # "Pro Max", "Ultra"
    must_match_keywords: list[str]
    exclude_keywords: list[str]
    expected_price_min: Optional[float]
    expected_price_max: Optional[float]
    

@dataclass  
class RelevanceResult:
    """Result of relevance check for a single listing."""
    listing_id: str
    is_relevant: bool
    confidence: float
    reason: str


# Keywords that indicate NOT a product (accessories, services, etc.)
EXCLUDE_KEYWORDS = [
    # Swedish
    "skal", "fodral", "laddare", "kabel", "adapter", "skärmskydd",
    "hörlurar", "airpods", "hållare", "stativ", "box", "lådor", "låda",
    "reparation", "byter", "byt ", "byte ", "lagning", "fix",
    "köpes", "sökes", "önskas", "vill ha", "letar efter",
    # English
    "case", "charger", "cable", "screen protector", "holder",
    "repair", "fix", "wanted", "looking for", "wtb",
]

# Keywords that indicate a service, not a product
SERVICE_KEYWORDS = [
    "reparation", "laga", "byter skärm", "byte av", "reparerar",
    "fix ", "fixa", "lagning", "rea på", "rabatt på reparation",
]


def understand_query(query: str) -> QueryUnderstanding:
    """
    Use AI to understand what the user is searching for.
    """
    llm = LLMClient()
    
    system_prompt = """Du analyserar sökfrågor för begagnade produkter på Blocket.
Avgör exakt vilken produkt användaren söker.

Svara ENDAST med giltig JSON:
{
    "product_type": "smartphone" | "laptop" | "tablet" | "camera" | "other",
    "brand": "Apple" | "Samsung" | etc | null,
    "model_line": "iPhone 15" | "Galaxy S24" | etc | null,
    "model_variant": "Pro Max" | "Ultra" | etc | null,
    "must_match_keywords": ["ord", "som", "måste", "finnas"],
    "exclude_keywords": ["ord", "som", "diskvalificerar"],
    "expected_price_min": 8000,
    "expected_price_max": 18000
}

Exempel:
- "iPhone 15 Pro Max" → model_line: "iPhone 15", variant: "Pro Max", expected: 10000-18000
- "MacBook Pro M3" → product_type: "laptop", model_line: "MacBook Pro", expected: 15000-35000"""

    user_prompt = f"Sökfråga: {query}"
    
    try:
        response = llm._call(
            system_prompt,
            user_prompt,
            response_format={"type": "json_object"},
        )
        data = json.loads(response)
        
        return QueryUnderstanding(
            product_type=data.get("product_type", "other"),
            brand=data.get("brand"),
            model_line=data.get("model_line"),
            model_variant=data.get("model_variant"),
            must_match_keywords=data.get("must_match_keywords", []),
            exclude_keywords=data.get("exclude_keywords", []) + EXCLUDE_KEYWORDS,
            expected_price_min=data.get("expected_price_min"),
            expected_price_max=data.get("expected_price_max"),
        )
    except Exception as e:
        # Fallback to basic parsing
        return QueryUnderstanding(
            product_type="other",
            brand=None,
            model_line=query,
            model_variant=None,
            must_match_keywords=query.lower().split(),
            exclude_keywords=EXCLUDE_KEYWORDS,
            expected_price_min=None,
            expected_price_max=None,
        )


def quick_filter_listings(
    listings: list[dict],
    query_understanding: QueryUnderstanding,
) -> list[dict]:
    """
    Fast pre-filter using rules BEFORE AI.
    Removes obvious non-matches to save API calls.
    """
    filtered = []
    
    for listing in listings:
        title = (listing.get("title") or "").lower()
        price = None
        price_data = listing.get("price", {})
        if isinstance(price_data, dict):
            price = price_data.get("amount")
        
        # Check exclude keywords
        is_excluded = False
        for kw in query_understanding.exclude_keywords:
            if kw.lower() in title:
                is_excluded = True
                break
        
        if is_excluded:
            continue
        
        # Check if it's a service
        is_service = False
        for kw in SERVICE_KEYWORDS:
            if kw.lower() in title:
                is_service = True
                break
        
        if is_service:
            continue
        
        # Price sanity check
        if price and query_understanding.expected_price_min:
            if price < query_understanding.expected_price_min * 0.1:
                # Price is less than 10% of expected minimum - probably not the product
                continue
        
        # Must have at least some query keywords
        if query_understanding.must_match_keywords:
            has_keyword = False
            for kw in query_understanding.must_match_keywords[:2]:  # Check first 2 keywords
                if kw.lower() in title:
                    has_keyword = True
                    break
            if not has_keyword:
                continue
        
        filtered.append(listing)
    
    return filtered


def ai_filter_listings(
    listings: list[dict],
    query: str,
    query_understanding: QueryUnderstanding,
    batch_size: int = 20,
) -> list[dict]:
    """
    Use AI to filter listings for relevance.
    Processes in batches to reduce API calls.
    """
    if not listings:
        return []
    
    llm = LLMClient()
    relevant_listings = []
    
    # Process in batches
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        
        # Prepare batch for AI
        batch_info = []
        for listing in batch:
            listing_id = str(listing.get("listing_id", ""))
            title = listing.get("title", "")
            price_data = listing.get("price", {})
            price = price_data.get("amount") if isinstance(price_data, dict) else None
            
            batch_info.append({
                "id": listing_id,
                "title": title,
                "price": price,
            })
        
        system_prompt = f"""Du filtrerar Blocket-annonser för relevans.

Användaren söker: "{query}"
Förväntat: {query_understanding.model_line or query} {query_understanding.model_variant or ''}
Förväntad prisintervall: {query_understanding.expected_price_min or '?'} - {query_understanding.expected_price_max or '?'} kr

För varje annons, avgör:
1. Är detta EXAKT den produkt som söks? (inte tillbehör, inte annan modell)
2. Är detta till SALU? (inte "köpes", inte reparationstjänst)
3. Är priset rimligt för produkten?

Svara ENDAST med JSON:
{{
    "results": [
        {{"id": "123", "relevant": true, "reason": "iPhone 15 Pro Max till salu"}},
        {{"id": "456", "relevant": false, "reason": "Detta är ett skal, inte en telefon"}}
    ]
}}

VIKTIGT:
- "iPhone 15" matchar INTE "iPhone 15 Pro Max" om användaren söker Pro Max
- Reparationstjänster är INTE relevanta
- Tillbehör (skal, laddare, kablar) är INTE relevanta
- Tomma lådor är INTE relevanta"""

        user_prompt = f"Annonser att filtrera:\n{json.dumps(batch_info, ensure_ascii=False, indent=2)}"
        
        try:
            response = llm._call(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            data = json.loads(response)
            
            # Map results back to listings
            results_map = {r["id"]: r["relevant"] for r in data.get("results", [])}
            
            for listing in batch:
                listing_id = str(listing.get("listing_id", ""))
                if results_map.get(listing_id, False):
                    relevant_listings.append(listing)
                    
        except Exception as e:
            # On error, include all from batch (fail open)
            relevant_listings.extend(batch)
    
    return relevant_listings


def deduplicate_listings(listings: list[dict]) -> list[dict]:
    """
    Remove duplicate listings based on URL and title+price.
    """
    seen_ids = set()
    seen_titles = set()
    unique = []
    
    for listing in listings:
        listing_id = str(listing.get("listing_id", ""))
        url = listing.get("url", "")
        title = (listing.get("title") or "").strip().lower()
        price_data = listing.get("price", {})
        price = price_data.get("amount") if isinstance(price_data, dict) else 0
        
        # Create dedup key
        dedup_key = f"{title}_{price}"
        
        if listing_id in seen_ids:
            continue
        if url and url in seen_ids:
            continue
        if dedup_key in seen_titles:
            continue
        
        seen_ids.add(listing_id)
        if url:
            seen_ids.add(url)
        seen_titles.add(dedup_key)
        unique.append(listing)
    
    return unique


def filter_and_prepare_listings(
    listings: list[dict],
    query: str,
) -> tuple[list[dict], QueryUnderstanding]:
    """
    Main entry point: understand query, filter listings, deduplicate.
    
    Returns:
        (filtered_listings, query_understanding)
    """
    # Step 1: Understand query
    query_understanding = understand_query(query)
    
    # Step 2: Quick rule-based filter
    quick_filtered = quick_filter_listings(listings, query_understanding)
    
    # Step 3: AI relevance filter
    ai_filtered = ai_filter_listings(quick_filtered, query, query_understanding)
    
    # Step 4: Deduplicate
    deduped = deduplicate_listings(ai_filtered)
    
    return deduped, query_understanding
