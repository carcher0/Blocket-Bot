"""
Debug panel component - transparency view for developers.
"""
import json
import streamlit as st
from typing import Optional

from v2.models.discovery import DomainDiscoveryOutput
from v2.models.preferences import PreferenceProfile
from v2.models.export import FullRunExport


def render_debug_panel(
    schema: Optional[DomainDiscoveryOutput] = None,
    preferences: Optional[PreferenceProfile] = None,
    results: Optional[FullRunExport] = None,
):
    """
    Render the debug/transparency panel.
    Shows internal state for debugging and understanding the system.
    """
    st.markdown("---")
    st.markdown("### 🔧 Debug Panel")
    
    tabs = st.tabs(["Schema", "Preferences", "Run Metadata", "Raw Export"])
    
    with tabs[0]:
        render_schema_debug(schema)
    
    with tabs[1]:
        render_preferences_debug(preferences)
    
    with tabs[2]:
        render_metadata_debug(results)
    
    with tabs[3]:
        render_raw_export(results)


def render_schema_debug(schema: Optional[DomainDiscoveryOutput]):
    """Render schema debugging info."""
    if schema is None:
        st.info("No schema loaded")
        return
    
    st.markdown(f"**Domain:** {schema.inferred_domain.domain_label}")
    st.markdown(f"**Confidence:** {schema.inferred_domain.confidence*100:.0f}%")
    st.markdown(f"**Sample size:** {schema.sample_size}")
    
    st.markdown("**Attributes:**")
    for attr in schema.attribute_candidates:
        st.markdown(f"- `{attr.name}` ({attr.type}) - weight: {attr.importance_weight}")
    
    st.markdown("**Questions:**")
    for q in schema.preference_questions:
        st.markdown(f"- {q.question_text} → `{q.maps_to_attribute}`")
    
    if schema.domain_risk_notes:
        st.markdown("**Risk notes:**")
        for note in schema.domain_risk_notes:
            st.markdown(f"- {note}")


def render_preferences_debug(preferences: Optional[PreferenceProfile]):
    """Render preferences debugging info."""
    if preferences is None:
        st.info("No preferences set")
        return
    
    st.markdown(f"**Query:** {preferences.user_query}")
    st.markdown(f"**Price range:** {preferences.min_price or '-'} - {preferences.max_price or '-'} kr")
    st.markdown(f"**Require shipping:** {preferences.require_shipping}")
    
    if preferences.selected_preferences:
        st.markdown("**Selected preferences:**")
        for pref in preferences.selected_preferences:
            st.markdown(f"- `{pref.attribute}` = {pref.value} ({pref.constraint_type})")
    
    if preferences.additional_requirements:
        st.markdown(f"**Additional:** {preferences.additional_requirements}")


def render_metadata_debug(results: Optional[FullRunExport]):
    """Render run metadata debugging info."""
    if results is None:
        st.info("No results available")
        return
    
    meta = results.metadata
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**Run ID:** `{meta.run_id}`")
        st.markdown(f"**Started:** {meta.started_at}")
        st.markdown(f"**Completed:** {meta.completed_at}")
    
    with col2:
        st.markdown(f"**Listings fetched:** {meta.total_listings_fetched}")
        st.markdown(f"**After filter:** {meta.listings_after_filter}")
        st.markdown(f"**Enriched:** {meta.listings_enriched}")
    
    if meta.errors:
        st.error(f"Errors: {meta.errors}")
    
    if meta.warnings:
        st.warning(f"Warnings: {meta.warnings}")


def render_raw_export(results: Optional[FullRunExport]):
    """Render raw JSON export."""
    if results is None:
        st.info("No results to export")
        return
    
    try:
        # Use minimal export to avoid huge JSON
        export_data = results.to_minimal_export()
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False, default=str)
        
        st.code(json_str, language="json")
        
        st.download_button(
            "📥 Download Full JSON",
            data=json.dumps(results.model_dump(), indent=2, ensure_ascii=False, default=str),
            file_name="debug_export.json",
            mime="application/json",
        )
    except Exception as e:
        st.error(f"Could not serialize: {e}")
