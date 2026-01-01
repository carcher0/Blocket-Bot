"""
Domain discovery service - AI-driven schema generation from listings.
"""
import json
import logging
from datetime import datetime
from typing import Optional

from ..models.listing import NormalizedListing
from ..models.discovery import (
    DomainDiscoveryOutput,
    InferredDomain,
    AttributeCandidate,
    PreferenceQuestion,
    DEFAULT_GENERIC_SCHEMA,
)
from .llm_client import LLMClient


logger = logging.getLogger(__name__)


DISCOVERY_SYSTEM_PROMPT = """You are an expert at analyzing marketplace listings.
Your task is to analyze a sample of listings and determine:
1. What product domain/category these listings belong to
2. What attributes are important for evaluating and comparing items in this domain
3. What questions should be asked to help buyers find the best match

CRITICAL: CONFIDENCE AND CLARIFICATION
- You MUST provide a confidence score (0.0-1.0) for your domain inference.
- Be HONEST about uncertainty. If the search term is ambiguous (like "4080" which could mean GPU or something else), set confidence LOW (< 0.7).
- If confidence < 0.7, you MUST provide a clarifying_question and clarifying_options to ask the user what they meant.
  - Example: For "4080", ask "Vad menar du med '4080'?" with options ["RTX 4080 grafikkort", "Modellnummer för annan produkt", "Annat"]

Analyze the listing texts carefully. Look for:
- Common attributes mentioned (size, condition, specifications, etc.)
- Terms that indicate quality or value
- Information that is often missing but would be helpful
- Domain-specific risk indicators

Return structured JSON following the exact schema provided.
Be specific to this domain - don't use generic attributes if domain-specific ones apply.
Use Swedish for user-facing text (question_text, display_name, clarifying_question, etc.)."""


DISCOVERY_USER_PROMPT_TEMPLATE = """Analyze these {count} listings for the search query.

Sample listing titles:
{titles}

Sample descriptions (if available):
{descriptions}

Sample prices: {prices}

Based on this data, generate a complete DomainDiscoveryOutput with:
1. inferred_domain: 
   - domain_label: What product type this is (be specific, e.g. "grafikkort", "smartphone", "cykel")
   - confidence: 0.0-1.0 (BE HONEST - if uncertain, use lower values)
   - subcategory: More specific if applicable
   - clarifying_question: REQUIRED if confidence < 0.7 (ask in Swedish what the user meant)
   - clarifying_options: 3-5 options for what they might mean (in Swedish)

2. attribute_candidates: 5-10 relevant attributes for this domain

3. preference_questions: 4-8 questions to ask the buyer (in Swedish)

4. domain_risk_notes: What to watch out for in this domain

IMPORTANT: If listings seem to be about different types of products (mixed results), 
set confidence LOW and ASK for clarification.

Return JSON matching this schema:
{schema}"""


class DomainDiscoveryService:
    """
    Discovers product domain and generates preference schema from listing data.
    Uses AI to analyze listings and extract relevant patterns.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def discover(
        self,
        listings: list[NormalizedListing],
        sample_size: int = 30,
    ) -> DomainDiscoveryOutput:
        """
        Analyze listings to discover domain and generate schema.

        Args:
            listings: Listings to analyze
            sample_size: How many to sample for analysis

        Returns:
            DomainDiscoveryOutput with inferred schema
        """
        if not listings:
            logger.warning("No listings to analyze, using generic schema")
            return DEFAULT_GENERIC_SCHEMA

        if not self.llm.is_available():
            logger.warning("LLM not available (no API key?), using generic schema")
            return DEFAULT_GENERIC_SCHEMA

        # Sample listings
        sample = listings[:sample_size]
        logger.info(f"Analyzing {len(sample)} listings for domain discovery")
        
        # Log sample titles for debugging
        sample_titles = [l.title for l in sample[:5] if l.title]
        logger.info(f"Sample titles: {sample_titles}")

        try:
            result = self._run_discovery(sample)
            logger.info(f"Discovery succeeded: domain='{result.inferred_domain.domain_label}' confidence={result.inferred_domain.confidence:.2f}")
            return result
        except Exception as e:
            logger.error(f"Discovery failed with error: {type(e).__name__}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return DEFAULT_GENERIC_SCHEMA

    def _run_discovery(
        self,
        sample: list[NormalizedListing],
    ) -> DomainDiscoveryOutput:
        """Run the AI discovery process."""
        # Prepare sample data
        titles = "\n".join(f"- {l.title}" for l in sample[:20] if l.title)
        
        descriptions = []
        for l in sample[:10]:
            if l.description:
                # Truncate long descriptions
                desc = l.description[:200] + "..." if len(l.description) > 200 else l.description
                descriptions.append(f"- {desc}")
        descriptions_text = "\n".join(descriptions) if descriptions else "(No descriptions available)"
        
        prices = [l.price for l in sample if l.price]
        prices_text = f"Range: {min(prices):.0f} - {max(prices):.0f} SEK" if prices else "(No prices)"

        # Get the schema
        schema_json = DomainDiscoveryOutput.model_json_schema()

        # Build prompt
        user_prompt = DISCOVERY_USER_PROMPT_TEMPLATE.format(
            count=len(sample),
            titles=titles,
            descriptions=descriptions_text,
            prices=prices_text,
            schema=json.dumps(schema_json, indent=2),
        )

        # Call LLM
        result = self.llm.call_with_schema(
            system_prompt=DISCOVERY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=DomainDiscoveryOutput,
        )

        # Add metadata
        result.sample_size = len(sample)
        result.discovery_timestamp = datetime.now().isoformat()

        logger.info(f"Discovered domain: {result.inferred_domain.domain_label} "
                    f"with {len(result.attribute_candidates)} attributes")
        
        return result

    def enhance_with_patterns(
        self,
        schema: DomainDiscoveryOutput,
        listings: list[NormalizedListing],
    ) -> DomainDiscoveryOutput:
        """
        Enhance a schema by finding additional patterns in listings.
        Uses regex to find common terms and add to evidence.
        """
        import re
        from collections import Counter

        # Combine all text
        all_text = " ".join(
            f"{l.title or ''} {l.description or ''}"
            for l in listings
        ).lower()

        # For each attribute, find evidence terms
        for attr in schema.attribute_candidates:
            terms_found = Counter()
            
            # Search for existing evidence terms
            for term in attr.evidence_terms:
                count = len(re.findall(re.escape(term.lower()), all_text))
                if count > 0:
                    terms_found[term] = count

            # Update prevalence estimate
            if listings:
                # Rough estimate: how many listings mention any evidence term
                mentions = 0
                for l in listings:
                    text = f"{l.title or ''} {l.description or ''}".lower()
                    if any(term.lower() in text for term in attr.evidence_terms):
                        mentions += 1
                attr.prevalence_estimate = mentions / len(listings)

        return schema
