"""
Smart Preferences module: Generate relevant preference questions based on query.
Uses GPT-5.2 to understand what questions matter for this specific product.
"""
import json
from typing import Optional
from dataclasses import dataclass

from .llm_client import LLMClient
from .ai_filter import QueryUnderstanding


@dataclass
class PreferenceQuestion:
    """A preference question to ask the user."""
    id: str
    question: str
    options: list[str]
    why: str  # Why this matters for the product
    default: Optional[str] = None


@dataclass
class UserPreferences:
    """User's answers to preference questions."""
    storage: Optional[str] = None  # "128 GB", "256 GB", etc.
    condition: Optional[str] = None  # "new", "like_new", "good", etc.
    min_battery: Optional[int] = None  # Minimum battery health %
    max_price: Optional[int] = None
    color: Optional[str] = None
    must_have_warranty: bool = False
    must_have_receipt: bool = False
    no_cracks: bool = True  # Default: no cracks
    unlocked: Optional[bool] = None
    extra_requirements: Optional[str] = None


def generate_preference_questions(
    query: str,
    query_understanding: QueryUnderstanding,
) -> list[PreferenceQuestion]:
    """
    Generate smart preference questions based on the query.
    Uses AI to understand what questions are relevant for this product.
    """
    llm = LLMClient()
    
    system_prompt = """Du genererar relevanta preferensfrågor för en produktsökning på Blocket.

Baserat på produkten, generera 3-5 frågor som FAKTISKT påverkar priset eller kvaliteten.
Varje fråga ska ha tydliga alternativ.

Svara ENDAST med giltig JSON:
{
    "questions": [
        {
            "id": "storage",
            "question": "Hur mycket lagring behöver du?",
            "options": ["64 GB", "128 GB", "256 GB", "512 GB", "Spelar ingen roll"],
            "why": "Påverkar pris med ~1000-3000 kr per steg",
            "default": "Spelar ingen roll"
        }
    ]
}

Viktiga frågor för smartphones:
- Lagring (påverkar pris mycket)
- Skick (nyskick vs använd)
- Batterihälsa (under 80% = billigare men behöver bytas snart)
- Sprickor (spricka i skärmen = stor rabatt)
- Olåst/operatörslåst (låst = svårsåld)

Viktiga frågor för laptops:
- RAM (8/16/32 GB)
- Lagring (SSD storlek)
- Processor (vilken generation)
- Skick

Anpassa frågor efter produkten!"""

    user_prompt = f"""Produkt: {query}
Typ: {query_understanding.product_type}
Märke: {query_understanding.brand or 'Okänt'}
Modell: {query_understanding.model_line or 'Okänt'} {query_understanding.model_variant or ''}
Förväntat pris: {query_understanding.expected_price_min or '?'} - {query_understanding.expected_price_max or '?'} kr

Generera relevanta preferensfrågor."""

    try:
        response = llm._call(
            system_prompt,
            user_prompt,
            response_format={"type": "json_object"},
        )
        data = json.loads(response)
        
        questions = []
        for q in data.get("questions", []):
            questions.append(PreferenceQuestion(
                id=q.get("id", ""),
                question=q.get("question", ""),
                options=q.get("options", []),
                why=q.get("why", ""),
                default=q.get("default"),
            ))
        return questions
        
    except Exception:
        # Fallback: Basic questions for smartphones
        if query_understanding.product_type == "smartphone":
            return [
                PreferenceQuestion(
                    id="storage",
                    question="Vilken lagring?",
                    options=["64 GB", "128 GB", "256 GB", "512 GB", "Spelar ingen roll"],
                    why="Påverkar pris",
                    default="Spelar ingen roll",
                ),
                PreferenceQuestion(
                    id="condition",
                    question="Vilket skick?",
                    options=["Endast nyskick", "Som ny/bra", "Accepterar repor", "Alla"],
                    why="Stor prisskillnad",
                    default="Som ny/bra",
                ),
                PreferenceQuestion(
                    id="battery",
                    question="Minsta batterihälsa?",
                    options=["90%+", "85%+", "80%+", "Spelar ingen roll"],
                    why="Under 80% = byt snart (~800kr)",
                    default="85%+",
                ),
                PreferenceQuestion(
                    id="cracks",
                    question="Accepterar sprickor i skärmen?",
                    options=["Nej, inga sprickor", "Ja, om priset är rätt"],
                    why="Skärmbyte kostar ~1500-3000kr",
                    default="Nej, inga sprickor",
                ),
            ]
        else:
            return []


def apply_preferences_to_filter(
    preferences: UserPreferences,
    query_understanding: QueryUnderstanding,
) -> dict:
    """
    Convert user preferences to filter dict for scoring.
    """
    filters = {}
    
    # Storage
    if preferences.storage and preferences.storage != "Spelar ingen roll":
        # Extract number from "128 GB"
        try:
            storage_num = int(preferences.storage.split()[0])
            filters["storage_gb"] = storage_num
        except ValueError:
            pass
    
    # Condition
    if preferences.condition:
        condition_map = {
            "Endast nyskick": "ny",
            "Som ny/bra": "som_ny",
            "Accepterar repor": "ok",
            "Alla": None,
        }
        filters["condition"] = condition_map.get(preferences.condition)
    
    # Battery
    if preferences.min_battery:
        filters["min_battery_health"] = preferences.min_battery
    
    # Max price
    if preferences.max_price:
        filters["max_price"] = preferences.max_price
    
    # Cracks
    filters["no_cracks"] = preferences.no_cracks
    
    # Warranty
    if preferences.must_have_warranty:
        filters["has_warranty"] = True
    
    # Receipt
    if preferences.must_have_receipt:
        filters["has_receipt"] = True
    
    # Unlocked
    if preferences.unlocked is not None:
        filters["unlocked"] = preferences.unlocked
    
    return filters


def parse_preference_answers(
    answers: dict[str, str],
) -> UserPreferences:
    """
    Parse user answers to preference questions into UserPreferences.
    
    Args:
        answers: Dict of question_id -> selected_option
    """
    prefs = UserPreferences()
    
    for question_id, answer in answers.items():
        if question_id == "storage":
            prefs.storage = answer
        elif question_id == "condition":
            prefs.condition = answer
        elif question_id == "battery":
            if answer == "90%+":
                prefs.min_battery = 90
            elif answer == "85%+":
                prefs.min_battery = 85
            elif answer == "80%+":
                prefs.min_battery = 80
        elif question_id == "cracks":
            prefs.no_cracks = "nej" in answer.lower() or "inga" in answer.lower()
        elif question_id == "max_price":
            try:
                prefs.max_price = int(answer.replace(" ", "").replace("kr", ""))
            except ValueError:
                pass
        elif question_id == "warranty":
            prefs.must_have_warranty = "ja" in answer.lower()
        elif question_id == "receipt":
            prefs.must_have_receipt = "ja" in answer.lower()
        elif question_id == "unlocked":
            prefs.unlocked = "olåst" in answer.lower() or "ja" in answer.lower()
    
    return prefs
