"""
Preferences models - user preference profile and constraints.
"""
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class PreferenceValue(BaseModel):
    """A single preference value with type."""
    attribute: str
    value: Any
    constraint_type: Literal["equals", "min", "max", "in", "not_in", "contains"] = "equals"
    is_hard_constraint: bool = Field(
        default=False,
        description="Hard constraints filter results, soft constraints affect score"
    )


class PreferenceProfile(BaseModel):
    """
    Complete user preference profile for a search.
    Combines the original query with selected preferences.
    """
    user_query: str = Field(description="Original search query")
    
    # Selected preferences from the wizard
    selected_preferences: list[PreferenceValue] = Field(
        default_factory=list,
        description="User-selected preference values"
    )
    
    # Hard constraints (must-haves/must-not-haves)
    hard_constraints: list[PreferenceValue] = Field(
        default_factory=list,
        description="Non-negotiable requirements"
    )
    
    # Optional: custom weights override
    weights_override: Optional[dict[str, float]] = Field(
        default=None,
        description="Override default attribute weights"
    )
    
    # Filter preferences
    max_price: Optional[float] = Field(default=None)
    min_price: Optional[float] = Field(default=None)
    locations: list[str] = Field(default_factory=list)
    require_shipping: bool = Field(default=False)
    
    # Free-text additions
    additional_requirements: Optional[str] = Field(
        default=None,
        description="Free-text requirements from user"
    )

    def get_preference_value(self, attribute: str) -> Optional[Any]:
        """Get the value for a specific attribute preference."""
        for pref in self.selected_preferences:
            if pref.attribute == attribute:
                return pref.value
        return None
    
    def get_hard_constraint(self, attribute: str) -> Optional[PreferenceValue]:
        """Get a hard constraint by attribute."""
        for constraint in self.hard_constraints:
            if constraint.attribute == attribute:
                return constraint
        return None
