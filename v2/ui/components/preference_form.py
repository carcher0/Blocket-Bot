"""
Preference form component - dynamic preference wizard.
"""
import streamlit as st
from typing import Any

from ...models.discovery import DomainDiscoveryOutput, PreferenceQuestion
from ...models.preferences import PreferenceProfile, PreferenceValue


def render_preferences_wizard(
    schema: DomainDiscoveryOutput,
    user_query: str,
) -> PreferenceProfile:
    """
    Render the dynamic preferences wizard based on discovered schema.
    
    Args:
        schema: The domain discovery output with preference questions
        user_query: The original search query
    
    Returns:
        PreferenceProfile with user selections
    """
    selected_prefs = []
    hard_constraints = []
    
    # Price preferences (always show)
    st.markdown("#### 💰 Pris")
    col1, col2 = st.columns(2)
    
    with col1:
        min_price = st.number_input(
            "Minpris (kr)",
            min_value=0,
            value=0,
            step=500,
            key="pref_min_price",
        )
    
    with col2:
        max_price = st.number_input(
            "Maxpris (kr)", 
            min_value=0,
            value=0,
            step=500,
            key="pref_max_price",
        )
    
    # Dynamic questions from schema
    if schema.preference_questions:
        st.markdown("#### 🎯 Preferenser")
        
        for question in schema.preference_questions:
            value = render_question(question)
            
            if value is not None:
                pref = PreferenceValue(
                    attribute=question.maps_to_attribute,
                    value=value,
                    constraint_type="in" if isinstance(value, list) else "equals",
                    is_hard_constraint=False,
                )
                selected_prefs.append(pref)
    
    # Shipping preference
    st.markdown("#### 📦 Leverans")
    require_shipping = st.checkbox(
        "Måste kunna skickas",
        value=False,
        key="pref_require_shipping",
    )
    
    # Additional requirements
    st.markdown("#### ✏️ Övriga krav")
    additional = st.text_area(
        "Fritext (valfritt)",
        placeholder="Skriv eventuella extra krav som inte finns ovan...",
        key="pref_additional",
        height=80,
    )
    
    return PreferenceProfile(
        user_query=user_query,
        selected_preferences=selected_prefs,
        hard_constraints=hard_constraints,
        min_price=min_price if min_price > 0 else None,
        max_price=max_price if max_price > 0 else None,
        require_shipping=require_shipping,
        additional_requirements=additional if additional else None,
    )


def render_question(question: PreferenceQuestion) -> Any:
    """Render a single preference question."""
    
    tooltip = question.tooltip or f"Baserat på mönster i annonser"
    
    if question.answer_type == "single_choice":
        options = ["Ingen preferens"] + question.options
        selected = st.selectbox(
            question.question_text,
            options=options,
            help=tooltip,
            key=f"q_{question.question_id}",
        )
        return selected if selected != "Ingen preferens" else None
    
    elif question.answer_type == "multi_choice":
        selected = st.multiselect(
            question.question_text,
            options=question.options,
            default=question.default_value if isinstance(question.default_value, list) else [],
            help=tooltip,
            key=f"q_{question.question_id}",
        )
        return selected if selected else None
    
    elif question.answer_type == "boolean":
        value = st.checkbox(
            question.question_text,
            value=bool(question.default_value),
            help=tooltip,
            key=f"q_{question.question_id}",
        )
        return value
    
    elif question.answer_type == "range":
        col1, col2 = st.columns(2)
        with col1:
            min_val = st.number_input(
                f"Min {question.maps_to_attribute}",
                value=0,
                key=f"q_{question.question_id}_min",
            )
        with col2:
            max_val = st.number_input(
                f"Max {question.maps_to_attribute}",
                value=0,
                key=f"q_{question.question_id}_max",
            )
        if min_val > 0 or max_val > 0:
            return {"min": min_val, "max": max_val}
        return None
    
    elif question.answer_type == "text":
        value = st.text_input(
            question.question_text,
            help=tooltip,
            key=f"q_{question.question_id}",
        )
        return value if value else None
    
    return None
