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
    Only removes OBVIOUS non-matches to save API calls.
    Should be LESS aggressive than AI filter.
    """
    filtered = []
    
    for listing in listings:
        title = (listing.get("title") or "").lower()
        price = None
        price_data = listing.get("price", {})
        if isinstance(price_data, dict):
            price = price_data.get("amount")
        
        # Only exclude OBVIOUS service listings (not products)
        is_service = False
        for kw in SERVICE_KEYWORDS:
            if kw.lower() in title:
                is_service = True
                break
        
        if is_service:
            continue
        
        # Only exclude if title is JUST an accessory word (not product + accessory)
        is_pure_accessory = False
        accessory_only_keywords = ["skal", "fodral", "laddare", "skärmskydd", "mobilfodral"]
        for kw in accessory_only_keywords:
            # If title starts with accessory word or is very short with just accessory
            if title.startswith(kw) or (len(title) < 30 and kw in title and "iphone" not in title and "samsung" not in title):
                is_pure_accessory = True
                break
        
        if is_pure_accessory:
            continue
        
        # Price sanity check - only reject VERY low prices
        if price and query_understanding.expected_price_min:
            if price < 200:  # Less than 200 kr - definitely not a phone
                continue
        
        # Don't require keyword matching here - let AI decide
        # This was too aggressive before
        
        filtered.append(listing)
    
    return filtered


def ai_filter_listings(
    listings: list[dict],
    query: str,
    query_understanding: QueryUnderstanding,
    batch_size: int = 25,  # Increased batch size
) -> list[dict]:
    """
    Use AI to filter listings for relevance.
    Processes in batches to reduce API calls.
    """
    if not listings:
        return []
    
    llm = LLMClient()
    relevant_listings = []
    
    # Build context about what we're looking for
    model_info = query_understanding.model_line or query
    variant_info = query_understanding.model_variant or ""
    
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
        
        # Improved prompt - less aggressive
        system_prompt = f"""Du är expert på att filtrera Blocket-annonser.

SÖKNING: "{query}"

UPPGIFT: Avgör för varje annons om den är RELEVANT för sökningen.

RELEVANT = Sant om:
✅ Annonsen säljer en {model_info} {variant_info} telefon/produkt
✅ Annonsen säljer en variant av samma modell-linje (t.ex. iPhone 15 / 15 Pro / 15 Pro Max för "iPhone 15" sökning)  
✅ Priset är rimligt för en telefon/produkt (ej under 500 kr)

RELEVANT = Falskt om:
❌ Annonsen är för TILLBEHÖR (skal, fodral, laddare, kablar, skärmskydd)
❌ Annonsen är för REPARATION/SERVICE (byt skärm, laga telefon)
❌ Annonsen är för TOMMA LÅDOR/KARTONGER
❌ Annonsen är "KÖPES"/"SÖKES" (inte säljes)
❌ Annonsen är för en HELT annan produkt (t.ex. iPhone 12 när sökning är iPhone 15)
❌ Annonsen är för AirPods, hörlurar, eller andra tillbehör

VIKTIGT: 
- Om du är OSÄKER, sätt relevant=true (bättre att inkludera för mycket)
- iPhone 15 Pro MAX får inkluderas även för sökning "iPhone 15 Pro Max" 
- Samma modell-serie ÄR relevant (iPhone 15 alla varianter)

Svara med JSON:
{{
    "results": [
        {{"id": "123", "relevant": true, "reason": "iPhone 15 Pro Max till salu"}},
        {{"id": "456", "relevant": false, "reason": "Skal/tillbehör"}}
    ]
}}"""

        user_prompt = f"Filtrera dessa annonser:\n{json.dumps(batch_info, ensure_ascii=False, indent=2)}"
        
        try:
            response = llm._call(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            data = json.loads(response)
            
            # Map results back to listings
            results_map = {str(r["id"]): r["relevant"] for r in data.get("results", [])}
            
            for listing in batch:
                listing_id = str(listing.get("listing_id", ""))
                # Default to True if not in results (fail open)
                if results_map.get(listing_id, True):
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
