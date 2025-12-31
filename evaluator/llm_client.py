"""
OpenAI LLM client with strict JSON validation.
Uses GPT-5.2 for attribute extraction and explanations.
"""
import json
import os
from typing import Any, Optional

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from .schemas import (
    ExtractedAttribute,
    LLMClassificationResponse,
    LLMExtractionResponse,
    LLMExplanationResponse,
    ClarifyingQuestion,
    ProductFamily,
)

# Load .env file
load_dotenv()


def load_api_key() -> str:
    """Load OpenAI API key from environment variable (.env file)."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    
    if not api_key:
        # Fallback to key.txt for backwards compatibility
        key_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "key.txt")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                content = f.read().strip()
                if "=" in content:
                    return content.split("=", 1)[1].strip()
                return content
    
    return api_key


class LLMClient:
    """OpenAI LLM client with strict JSON validation."""

    def __init__(self, model: str = "gpt-5.2"):
        self.api_key = load_api_key()
        if not self.api_key:
            raise ValueError("No OpenAI API key found. Add it to key.txt or set OPENAI_API_KEY.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    def _call(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: Optional[dict] = None,
    ) -> str:
        """Make an API call and return the response text."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,  # Low temperature for consistency
        }
        
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def classify_query(
        self,
        query: str,
        sample_titles: list[str],
        sample_prices: list[Optional[float]],
    ) -> LLMClassificationResponse:
        """
        Classify a search query to determine product family and key attributes.
        Used when mechanical analysis is uncertain.
        """
        system_prompt = """Du är en expert på att klassificera produkter på Blocket.
Analysera sökningen och annonserna för att avgöra:
1. Vilken produktfamilj det handlar om (phone/laptop/tablet/camera/unknown)
2. Vilka nyckelattribut som påverkar priset
3. Om det finns oklarheter som kräver förtydligande

Svara ENDAST med giltig JSON enligt detta schema:
{
    "product_family": "phone|laptop|tablet|camera|unknown",
    "confidence": 0.0-1.0,
    "key_attributes": ["attribut1", "attribut2"],
    "evidence": ["exempel från titlar"],
    "clarifying_questions": ["fråga om oklart"]
}"""

        # Build user prompt with samples
        samples = []
        for title, price in zip(sample_titles[:15], sample_prices[:15]):
            price_str = f"{price:,.0f} kr" if price else "N/A"
            samples.append(f"- {title} ({price_str})")
        
        user_prompt = f"""Sökterm: "{query}"

Exempelannonser:
{chr(10).join(samples)}

Klassificera denna sökning."""

        try:
            response = self._call(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            data = json.loads(response)
            return LLMClassificationResponse(
                product_family=data.get("product_family", "unknown"),
                confidence=data.get("confidence", 0.5),
                key_attributes=data.get("key_attributes", []),
                evidence=data.get("evidence", []),
                clarifying_questions=data.get("clarifying_questions", []),
            )
        except (json.JSONDecodeError, ValidationError) as e:
            return LLMClassificationResponse(
                product_family="unknown",
                confidence=0.0,
                key_attributes=[],
                evidence=[f"LLM error: {str(e)}"],
                clarifying_questions=[],
            )

    def extract_attributes(
        self,
        title: str,
        description: Optional[str] = None,
        attribute_schema: Optional[dict[str, str]] = None,
    ) -> list[ExtractedAttribute]:
        """
        Extract attributes from listing text using LLM.
        Used as fallback when regex extraction fails.
        """
        system_prompt = """Du är expert på att extrahera produktattribut från Blocket-annonser.
Extrahera ENDAST attribut som tydligt nämns i texten.
Om något är osäkert, ange lägre confidence.

Svara ENDAST med giltig JSON enligt detta schema:
{
    "attributes": [
        {
            "name": "attributnamn",
            "value": "värde eller null",
            "confidence": 0.0-1.0,
            "evidence_span": "texten som stödjer"
        }
    ]
}

Vanliga attribut för telefoner:
- model_variant: "iPhone 15 Pro", "Samsung Galaxy S24" etc
- storage_gb: 64, 128, 256, 512, 1024
- condition: "ny", "som_ny", "bra", "ok", "defekt"
- has_cracks: true/false
- battery_health: 0-100
- has_warranty: true/false
- has_receipt: true/false
- is_locked: true/false (operatörslåst)
- color: färg"""

        text = title
        if description:
            text += f"\n\nBeskrivning:\n{description}"

        user_prompt = f"""Extrahera attribut från denna annons:

{text}"""

        try:
            response = self._call(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            data = json.loads(response)
            
            attributes = []
            for attr in data.get("attributes", []):
                attributes.append(ExtractedAttribute(
                    name=attr.get("name", ""),
                    value=attr.get("value"),
                    confidence=attr.get("confidence", 0.5),
                    evidence_span=attr.get("evidence_span"),
                    source="llm",
                ))
            return attributes
        except (json.JSONDecodeError, ValidationError):
            return []

    def generate_explanations(
        self,
        listings: list[dict],
        preferences: dict,
        comps_summary: dict,
    ) -> tuple[list[dict], list[ClarifyingQuestion]]:
        """
        Generate explanations for top picks and suggest follow-up questions.
        """
        system_prompt = """Du är en expert på begagnatmarknaden för elektronik.
Generera korta, användbara förklaringar för varför dessa annonser är bra köp.
Föreslå också frågor användaren bör ställa till säljaren.

Svara ENDAST med giltig JSON:
{
    "explanations": [
        {
            "listing_id": "id",
            "summary": "1-2 meningar om varför detta är bra",
            "check_list": ["fråga 1", "fråga 2"]
        }
    ],
    "questions": [
        {
            "question": "fråga till användaren",
            "options": ["alternativ1", "alternativ2"],
            "reason": "varför frågan är viktig"
        }
    ]
}"""

        # Build listing summaries
        listing_summaries = []
        for l in listings[:5]:
            listing_summaries.append({
                "id": l.get("listing_id"),
                "title": l.get("title"),
                "price": l.get("asking_price"),
                "scores": l.get("scores", {}),
            })

        user_prompt = f"""Toppannonser:
{json.dumps(listing_summaries, indent=2, ensure_ascii=False)}

Användarpreferenser:
{json.dumps(preferences, indent=2, ensure_ascii=False)}

Marknadsdata:
{json.dumps(comps_summary, indent=2, ensure_ascii=False)}

Generera förklaringar och förslag."""

        try:
            response = self._call(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            data = json.loads(response)
            
            explanations = data.get("explanations", [])
            questions = []
            for q in data.get("questions", []):
                questions.append(ClarifyingQuestion(
                    question=q.get("question", ""),
                    options=q.get("options", []),
                    reason=q.get("reason", ""),
                    information_gain=0.7,
                ))
            
            return explanations, questions
        except (json.JSONDecodeError, ValidationError):
            return [], []

    def analyze_risk(
        self,
        title: str,
        description: str,
        price: float,
        market_median: float,
    ) -> dict:
        """
        Analyze listing for potential risks using LLM.
        """
        system_prompt = """Du analyserar Blocket-annonser för potentiella varningssignaler.
Identifiera ENDAST uppenbara varningssignaler, inte spekulationer.

Svara ENDAST med giltig JSON:
{
    "risk_level": "low|medium|high",
    "flags": ["flagga1", "flagga2"],
    "explanation": "kort förklaring"
}

Vanliga varningssignaler:
- Extremt lågt pris jämfört med marknad
- Stressande språk ("måste bort idag")
- Udda betalningskrav
- Vaga beskrivningar
- Motsägelser i texten"""

        price_diff = ((market_median - price) / market_median * 100) if market_median > 0 else 0

        user_prompt = f"""Annons:
Titel: {title}
Pris: {price:,.0f} kr (marknad: {market_median:,.0f} kr, {price_diff:+.0f}% skillnad)

Beskrivning:
{description[:500] if description else "(ingen beskrivning)"}

Analysera risker."""

        try:
            response = self._call(
                system_prompt,
                user_prompt,
                response_format={"type": "json_object"},
            )
            return json.loads(response)
        except (json.JSONDecodeError, ValidationError):
            return {"risk_level": "unknown", "flags": [], "explanation": "Kunde inte analysera"}
