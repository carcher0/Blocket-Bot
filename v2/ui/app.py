"""
Blocket Bot 2.0 - Modern Purchase Assistant

A professional Streamlit UI with Blocket-inspired design.
"""
import streamlit as st
from datetime import datetime
from typing import Optional

from ..config import get_config
from ..client import BlocketClient
from ..models.preferences import PreferenceProfile, PreferenceValue
from ..models.discovery import DomainDiscoveryOutput, DEFAULT_GENERIC_SCHEMA
from ..pipeline import run_pipeline
from ..ai import DomainDiscoveryService

from .styles import inject_custom_css
from .components.search_input import render_search_section
from .components.preference_form import render_preferences_wizard
from .components.result_card import render_results_section
from .components.detail_panel import render_detail_panel
from .components.debug_panel import render_debug_panel


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "client": None,
        "listings": [],
        "schema": None,
        "preferences": None,
        "results": None,
        "selected_listing_id": None,
        "step": "search",  # search, preferences, results
        "show_debug": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def main():
    """Main application entry point."""
    config = get_config()
    
    # Page config
    st.set_page_config(
        page_title=config.ui.page_title,
        page_icon=config.ui.page_icon,
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    
    # Inject custom CSS
    inject_custom_css()
    
    # Initialize state
    init_session_state()
    
    # Initialize client
    if st.session_state.client is None:
        st.session_state.client = BlocketClient()
    
    # Header
    render_header()
    
    # Main content based on current step
    step = st.session_state.step
    
    if step == "search":
        render_search_step()
    elif step == "preferences":
        render_preferences_step()
    elif step == "results":
        render_results_step()
    
    # Debug panel (if enabled)
    if config.enable_debug_panel and st.session_state.show_debug:
        render_debug_panel(
            schema=st.session_state.schema,
            preferences=st.session_state.preferences,
            results=st.session_state.results,
        )


def render_header():
    """Render the app header."""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("""
        <div class="app-header">
            <h1>🔍 Blocket Bot 2.0</h1>
            <p class="subtitle">Din AI-drivna köpassistent för begagnat</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        # Debug toggle
        if get_config().enable_debug_panel:
            st.session_state.show_debug = st.checkbox(
                "🔧 Debug",
                value=st.session_state.show_debug,
                key="debug_toggle"
            )


def render_search_step():
    """Render the search/intent step."""
    st.markdown("### Vad letar du efter?")
    
    query, filters = render_search_section()
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔍 Sök på Blocket", type="primary", use_container_width=True):
            if query:
                with st.spinner("Hämtar annonser från Blocket..."):
                    try:
                        listings = st.session_state.client.search(
                            query=query,
                            locations=filters.get("locations"),
                            sort_order=filters.get("sort_order"),
                            max_pages=5,
                        )
                        st.session_state.listings = listings
                        st.session_state.user_query = query
                        st.session_state.search_filters = filters
                        
                        if listings:
                            st.success(f"✓ Hittade {len(listings)} annonser")
                            
                            # Run domain discovery
                            with st.spinner("Analyserar marknaden..."):
                                discovery = DomainDiscoveryService()
                                schema = discovery.discover(listings)
                                st.session_state.schema = schema
                            
                            st.session_state.step = "preferences"
                            st.rerun()
                        else:
                            st.warning("Inga annonser hittades. Prova en annan sökning.")
                    except Exception as e:
                        st.error(f"Sökning misslyckades: {e}")
            else:
                st.warning("Skriv in vad du söker efter")


def render_preferences_step():
    """Render the preferences wizard step."""
    schema = st.session_state.schema
    
    if schema is None:
        schema = DEFAULT_GENERIC_SCHEMA
    
    st.markdown(f"### 📋 Preferenser för: *{st.session_state.user_query}*")
    
    # Show domain info
    if schema.inferred_domain:
        st.markdown(f"""
        <div class="domain-badge">
            <span class="domain-label">{schema.inferred_domain.domain_label.title()}</span>
            <span class="confidence">({schema.inferred_domain.confidence*100:.0f}% säkerhet)</span>
        </div>
        """, unsafe_allow_html=True)
    
    # Preference form
    preferences = render_preferences_wizard(schema, st.session_state.user_query)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← Tillbaka", use_container_width=True):
            st.session_state.step = "search"
            st.rerun()
    
    with col3:
        if st.button("Analysera →", type="primary", use_container_width=True):
            st.session_state.preferences = preferences
            
            with st.spinner("Analyserar och rankar annonser..."):
                try:
                    results = run_pipeline(
                        listings=st.session_state.listings,
                        preferences=preferences,
                        schema=schema,
                        top_k=10,
                    )
                    st.session_state.results = results
                    st.session_state.step = "results"
                    st.rerun()
                except Exception as e:
                    st.error(f"Analys misslyckades: {e}")


def render_results_step():
    """Render the results step."""
    results = st.session_state.results
    
    if results is None:
        st.warning("Inga resultat att visa")
        if st.button("← Börja om"):
            st.session_state.step = "search"
            st.rerun()
        return
    
    st.markdown(f"### 🏆 Topp 10 för: *{st.session_state.user_query}*")
    
    # Market summary
    if results.market_summary:
        summary = results.market_summary
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Annonser", summary.get("total_listings", 0))
        col2.metric("Median", f"{summary.get('median_price', 0):,.0f} kr")
        col3.metric("Lägsta", f"{summary.get('min_price', 0):,.0f} kr")
        col4.metric("Högsta", f"{summary.get('max_price', 0):,.0f} kr")
    
    st.markdown("---")
    
    # Results
    render_results_section(results.top_results)
    
    # Navigation
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("← Ändra preferenser", use_container_width=True):
            st.session_state.step = "preferences"
            st.rerun()
    
    with col2:
        if st.button("🔄 Ny sökning", use_container_width=True):
            st.session_state.step = "search"
            st.session_state.listings = []
            st.session_state.results = None
            st.rerun()
    
    with col3:
        # Export button
        if results.top_results:
            export_data = results.to_minimal_export()
            import json
            st.download_button(
                "📥 Exportera JSON",
                data=json.dumps(export_data, indent=2, ensure_ascii=False),
                file_name=f"blocket_results_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
