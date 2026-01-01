"""
Blocket Bot - Streamlit UI Testpanel

A local web UI for searching Blocket listings, managing saved searches (watches),
and exporting results with preferences for future evaluation logic.
"""
import json
import os
from datetime import datetime, timezone

import streamlit as st

from blocket_client import BlocketClient
from normalization import (
    Export,
    Filters,
    Preferences,
    create_export,
    normalize_listings,
)
from storage import (
    create_watch,
    delete_watch,
    filter_new_listings,
    get_watch,
    get_watches,
    mark_listings_seen,
)


# Ensure exports directory exists
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")
os.makedirs(EXPORTS_DIR, exist_ok=True)


# Page configuration
st.set_page_config(
    page_title="Blocket Bot - Testpanel",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for premium dark theme styling
st.markdown("""
<style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Global styles */
    .stApp {
        font-family: 'Inter', sans-serif;
    }
    
    /* Header styling */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    
    h2, h3 {
        color: #e0e0e0;
        font-weight: 600;
    }
    
    /* Card styling with glassmorphism */
    .deal-card {
        background: linear-gradient(135deg, rgba(30, 30, 46, 0.9) 0%, rgba(45, 45, 68, 0.9) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .deal-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(102, 126, 234, 0.2);
    }
    
    /* Score badges */
    .score-badge {
        display: inline-block;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 1.2rem;
    }
    
    .score-excellent {
        background: linear-gradient(135deg, #00c853 0%, #00e676 100%);
        color: white;
    }
    
    .score-good {
        background: linear-gradient(135deg, #ffc107 0%, #ffca28 100%);
        color: #1a1a2e;
    }
    
    .score-poor {
        background: linear-gradient(135deg, #ff5252 0%, #ff1744 100%);
        color: white;
    }
    
    /* Metric cards */
    .metric-card {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #667eea;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Risk indicators */
    .risk-low {
        color: #00c853;
    }
    
    .risk-medium {
        color: #ffc107;
    }
    
    .risk-high {
        color: #ff5252;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
    }
    
    /* Progress/loading animation */
    @keyframes pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    
    .loading {
        animation: pulse 1.5s infinite;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    /* Table styling */
    .dataframe {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Tags/chips */
    .tag {
        display: inline-block;
        background: rgba(102, 126, 234, 0.2);
        color: #667eea;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        margin-right: 0.5rem;
        margin-bottom: 0.5rem;
    }
    
    .tag-warning {
        background: rgba(255, 193, 7, 0.2);
        color: #ffc107;
    }
    
    .tag-success {
        background: rgba(0, 200, 83, 0.2);
        color: #00c853;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
    }
    
    /* Input fields */
    .stTextInput > div > div > input,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
    }
    
    /* Top pick ranking */
    .rank-1 { color: #ffd700; }  /* Gold */
    .rank-2 { color: #c0c0c0; }  /* Silver */
    .rank-3 { color: #cd7f32; }  /* Bronze */
</style>
""", unsafe_allow_html=True)


# Initialize session state
if "client" not in st.session_state:
    st.session_state.client = BlocketClient()
if "search_results" not in st.session_state:
    st.session_state.search_results = []
if "watch_results" not in st.session_state:
    st.session_state.watch_results = []
if "current_watch_id" not in st.session_state:
    st.session_state.current_watch_id = None
if "evaluation_results" not in st.session_state:
    st.session_state.evaluation_results = None


def render_preferences_form(prefix: str = "") -> Preferences:
    """Render preferences form and return Preferences object."""
    st.subheader("📋 Preferenser (för framtida värdering)")
    st.caption("Dessa sparas men påverkar inte sökningen än")

    col1, col2 = st.columns(2)

    with col1:
        condition = st.selectbox(
            "Skick",
            options=[None, "ny", "som_ny", "bra", "ok", "defekt"],
            format_func=lambda x: {
                None: "-- Välj --",
                "ny": "Ny",
                "som_ny": "Som ny",
                "bra": "Bra",
                "ok": "OK",
                "defekt": "Defekt",
            }.get(x, x),
            key=f"{prefix}condition",
        )

        no_cracks = st.checkbox("❌ Inga sprickor", key=f"{prefix}no_cracks")

        min_battery = st.slider(
            "🔋 Minsta batterihälsa (%)",
            min_value=0,
            max_value=100,
            value=0,
            key=f"{prefix}min_battery",
        )
        min_battery_val = min_battery if min_battery > 0 else None

    with col2:
        price_col1, price_col2 = st.columns(2)
        with price_col1:
            min_price = st.number_input(
                "Min pris (kr)",
                min_value=0,
                value=0,
                step=100,
                key=f"{prefix}min_price",
            )
        with price_col2:
            max_price = st.number_input(
                "Max pris (kr)",
                min_value=0,
                value=0,
                step=100,
                key=f"{prefix}max_price",
            )

        location_req = st.text_input(
            "📍 Platskrav",
            placeholder="t.ex. inom 50km från Stockholm",
            key=f"{prefix}location_req",
        )

        shipping_required = st.checkbox("📦 Leverans/frakt krävs", key=f"{prefix}shipping")

    other_req = st.text_area(
        "📝 Övriga krav",
        placeholder="Andra krav som ska beaktas vid värdering...",
        key=f"{prefix}other_req",
    )

    return Preferences(
        condition=condition,
        no_cracks=no_cracks,
        min_battery_health=min_battery_val,
        min_price=min_price if min_price > 0 else None,
        max_price=max_price if max_price > 0 else None,
        location_requirements=location_req if location_req else None,
        shipping_required=shipping_required,
        other_requirements=other_req if other_req else None,
    )


def render_filters_form(prefix: str = "") -> tuple[list[str], str | None, str | None]:
    """Render filter form and return (locations, category, sort_order)."""
    with st.expander("🔧 Filter (valfritt)"):
        locations = st.multiselect(
            "Platser",
            options=st.session_state.client.get_location_options(),
            format_func=lambda x: x.replace("_", " ").title(),
            key=f"{prefix}locations",
        )

        sort_order = st.selectbox(
            "Sortering",
            options=[None] + st.session_state.client.get_sort_options(),
            format_func=lambda x: {
                None: "-- Standard --",
                "relevance": "Relevans",
                "price_asc": "Pris (lägst först)",
                "price_desc": "Pris (högst först)",
                "published_desc": "Datum (nyast först)",
                "published_asc": "Datum (äldst först)",
            }.get(x, x),
            key=f"{prefix}sort_order",
        )

        # Category input (text for now since we need to map to enum)
        category = st.text_input(
            "Kategori (valfritt)",
            placeholder="t.ex. ELEKTRONIK",
            key=f"{prefix}category",
        )

    return locations, category if category else None, sort_order


def render_results_table(listings: list[dict], show_new_indicator: bool = False, seen_ids: set = None):
    """Render listings in a table format."""
    if not listings:
        st.info("Inga resultat att visa")
        return

    # Create display data
    display_data = []
    for listing in listings:
        price_obj = listing.get("price", {})
        if isinstance(price_obj, dict):
            price_amount = price_obj.get("amount")
            price_str = f"{price_amount:,.0f} kr" if price_amount else "Ej angivet"
        else:
            price_str = str(price_obj) if price_obj else "Ej angivet"

        is_new = True
        if show_new_indicator and seen_ids:
            listing_id = listing.get("listing_id")
            is_new = listing_id not in seen_ids if listing_id else True

        display_data.append({
            "🆕": "✅" if (show_new_indicator and is_new) else "",
            "Titel": listing.get("title", "N/A"),
            "Pris": price_str,
            "Plats": listing.get("location", "N/A"),
            "Publicerad": listing.get("published_at", "N/A")[:10] if listing.get("published_at") else "N/A",
            "URL": listing.get("url", ""),
        })

    st.dataframe(
        display_data,
        column_config={
            "URL": st.column_config.LinkColumn("Länk", display_text="Öppna"),
        },
        hide_index=True,
        use_container_width=True,
    )


def export_to_json(
    listings: list[dict],
    query: str = None,
    watch_id: str = None,
    filters: Filters = None,
    preferences: Preferences = None,
    mode: str = "full",
) -> str:
    """Export listings to JSON file and return file path."""
    # Create export object
    export_obj = create_export(
        listings=listings,
        query=query,
        watch_id=watch_id,
        filters=filters,
        preferences=preferences,
        mode=mode,
    )

    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    query_slug = (query or "export").replace(" ", "_")[:20]
    filename = f"blocket_{query_slug}_{mode}_{timestamp}.json"
    filepath = os.path.join(EXPORTS_DIR, filename)

    # Write to file
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(export_obj.model_dump(), f, indent=2, ensure_ascii=False)

    return filepath


# Sidebar navigation
st.sidebar.title("🤖 Blocket Bot")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigation",
    options=["🔍 Sök", "🎯 Evaluering", "👁️ Bevakningar", "ℹ️ Om"],
    label_visibility="collapsed",
)


# === SEARCH PAGE ===
if page == "🔍 Sök":
    st.title("🔍 Sökning")
    st.markdown("Sök efter annonser på Blocket")

    # Search input
    query = st.text_input(
        "Sökord",
        placeholder="t.ex. iPhone 15, MacBook Pro...",
        key="search_query",
    )

    # Filters
    locations, category, sort_order = render_filters_form("search_")

    # Search button
    col1, col2 = st.columns([1, 4])
    with col1:
        search_clicked = st.button("🔍 Sök", type="primary", use_container_width=True)

    if search_clicked and query:
        with st.spinner("Söker på Blocket..."):
            try:
                raw_results = st.session_state.client.search(
                    query=query,
                    locations=locations if locations else None,
                    category=category,
                    sort_order=sort_order,
                )
                # Normalize results
                normalized = normalize_listings(raw_results)
                st.session_state.search_results = [l.model_dump() for l in normalized]
                st.success(f"Hittade {len(normalized)} annonser")
            except Exception as e:
                st.error(f"Sökningen misslyckades: {str(e)}")

    # Display results
    if st.session_state.search_results:
        st.markdown("---")
        st.subheader(f"📋 Resultat ({len(st.session_state.search_results)} annonser)")

        render_results_table(st.session_state.search_results)

        # Export button
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("📥 Exportera JSON", type="secondary"):
                filters = Filters(
                    locations=locations,
                    category=category,
                    sort_order=sort_order,
                )
                filepath = export_to_json(
                    listings=st.session_state.search_results,
                    query=query,
                    filters=filters,
                    mode="full",
                )
                st.success(f"Exporterad till: {filepath}")

        with col2:
            # Download button
            if st.session_state.search_results:
                filters = Filters(
                    locations=locations,
                    category=category,
                    sort_order=sort_order,
                )
                export_obj = create_export(
                    listings=st.session_state.search_results,
                    query=query,
                    filters=filters,
                    mode="full",
                )
                json_str = json.dumps(export_obj.model_dump(), indent=2, ensure_ascii=False)
                st.download_button(
                    label="💾 Ladda ner",
                    data=json_str,
                    file_name=f"blocket_{query.replace(' ', '_')[:20]}.json",
                    mime="application/json",
                )


# === EVALUATION PAGE ===
elif page == "🎯 Evaluering":
    st.title("🎯 Evaluering")
    st.markdown("Hitta de bästa köpen baserat på marknadspris och dina preferenser")

    # Search input
    eval_query = st.text_input(
        "Sökord",
        placeholder="t.ex. iPhone 15",
        key="eval_query",
    )

    # Preferences in expander
    with st.expander("📋 Preferenser", expanded=True):
        pref_col1, pref_col2 = st.columns(2)
        
        with pref_col1:
            eval_condition = st.selectbox(
                "Minst skick",
                options=[None, "ny", "som_ny", "bra", "ok"],
                format_func=lambda x: {
                    None: "-- Alla --",
                    "ny": "Ny",
                    "som_ny": "Som ny",
                    "bra": "Bra",
                    "ok": "OK",
                }.get(x, x),
                key="eval_condition",
            )
            eval_no_cracks = st.checkbox("❌ Inga sprickor", key="eval_no_cracks")
            eval_min_battery = st.slider("🔋 Minsta batterihälsa (%)", 0, 100, 0, key="eval_battery")
        
        with pref_col2:
            eval_max_price = st.number_input("Max pris (kr)", min_value=0, value=0, step=500, key="eval_max_price")
            eval_warranty = st.checkbox("📜 Helst garanti/kvitto", key="eval_warranty")
            eval_unlocked = st.checkbox("🔓 Olåst", key="eval_unlocked")

    # Run evaluation button
    if st.button("🎯 Analysera marknaden", type="primary", use_container_width=True):
        if not eval_query:
            st.error("Ange ett sökord!")
        else:
            with st.spinner("Söker och analyserar... (detta kan ta en stund)"):
                try:
                    # Fetch listings
                    raw_results = st.session_state.client.search(query=eval_query)
                    normalized = normalize_listings(raw_results)
                    listings = [l.model_dump() for l in normalized]
                    
                    # Build preferences dict
                    prefs = {
                        "condition": eval_condition,
                        "no_cracks": eval_no_cracks,
                        "min_battery_health": eval_min_battery if eval_min_battery > 0 else None,
                        "max_price": eval_max_price if eval_max_price > 0 else None,
                        "has_warranty": eval_warranty,
                        "unlocked": eval_unlocked,
                    }
                    
                    # Run evaluation
                    from evaluator.pipeline import run_evaluation
                    result = run_evaluation(
                        query=eval_query,
                        listings=listings,
                        preferences=prefs,
                        top_k=10,
                    )
                    st.session_state.evaluation_results = result
                    st.success(f"Analyserade {result.total_evaluated} annonser!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fel vid evaluering: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())

    # Display results
    if st.session_state.evaluation_results:
        result = st.session_state.evaluation_results
        
        # Query analysis info
        with st.expander("📊 Marknadsanalys", expanded=False):
            qa = result.query_analysis
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Produkttyp", qa.product_family.value.title())
            with col2:
                st.metric("Konfidensgrad", f"{qa.confidence:.0%}")
            with col3:
                st.metric("Analyserade annonser", result.total_evaluated)
            
            if result.data_quality_notes:
                st.warning("\n".join(result.data_quality_notes))

        # Comps summary
        if result.comps_groups:
            with st.expander("💰 Prisreferenser (Comps)", expanded=False):
                for group in result.comps_groups[:5]:
                    if group.stats:
                        key_str = f"{group.comps_key.model_variant or 'Alla'} / {group.comps_key.storage_bucket or 'Alla'} / {group.comps_key.condition_bucket or 'Alla'}"
                        st.markdown(f"**{key_str}**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Median", f"{group.stats.median_price:,.0f} kr")
                        with col2:
                            st.metric("25-75%", f"{group.stats.q1:,.0f} - {group.stats.q3:,.0f} kr")
                        with col3:
                            st.metric("Antal", group.stats.n)
                        with col4:
                            sufficient = "✅" if group.is_sufficient else "⚠️"
                            st.metric("Status", sufficient)
                        st.markdown("---")

        # Top picks
        st.subheader(f"🏆 Topp {len(result.ranked_listings)} köptips")
        
        # Filter toggles
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            show_low_risk_only = st.checkbox("Endast låg risk", key="filter_low_risk")
        with filter_col2:
            show_high_value_only = st.checkbox("Endast bra pris (>60)", key="filter_high_value")
        
        # Display each top pick
        for listing in result.ranked_listings:
            # Apply filters
            if show_low_risk_only and listing.scores.risk_assessment.score >= 50:
                continue
            if show_high_value_only and listing.scores.value_score.score < 60:
                continue
            
            with st.container():
                # Header with title and final score
                title_col, score_col = st.columns([4, 1])
                with title_col:
                    rank_emoji = "🥇" if listing.rank == 1 else "🥈" if listing.rank == 2 else "🥉" if listing.rank == 3 else f"#{listing.rank}"
                    st.markdown(f"### {rank_emoji} {listing.title or 'Okänd titel'}")
                with score_col:
                    score_color = "green" if listing.scores.final_score >= 60 else "orange" if listing.scores.final_score >= 40 else "red"
                    st.markdown(f"<h2 style='color:{score_color};text-align:center'>{listing.scores.final_score:.0f}</h2>", unsafe_allow_html=True)
                
                # Price and location
                info_col1, info_col2, info_col3 = st.columns(3)
                with info_col1:
                    st.markdown(f"**Pris:** {listing.asking_price:,.0f} kr" if listing.asking_price else "**Pris:** Ej angivet")
                with info_col2:
                    st.markdown(f"**Plats:** {listing.location or 'Ej angivet'}")
                with info_col3:
                    st.markdown(f"[🔗 Öppna annons]({listing.url})")
                
                # Score breakdown
                score_col1, score_col2, score_col3 = st.columns(3)
                with score_col1:
                    vs = listing.scores.value_score
                    delta_str = f"{vs.deal_delta:+.0%}" if vs.deal_delta else ""
                    st.metric(
                        "💰 Prisvärdhet",
                        f"{vs.score:.0f}",
                        delta=delta_str,
                        help=f"Baserat på {vs.comps_n} jämförbara annonser"
                    )
                with score_col2:
                    ps = listing.scores.preference_score
                    st.metric(
                        "✅ Preferensmatch",
                        f"{ps.score:.0f}",
                        help="Hur väl annonsen matchar dina krav"
                    )
                with score_col3:
                    rs = listing.scores.risk_assessment
                    risk_str = "Låg" if rs.score < 25 else "Medel" if rs.score < 50 else "Hög"
                    st.metric(
                        "⚠️ Risk",
                        f"{rs.score:.0f} ({risk_str})",
                        delta=None,
                        help="Lägre är bättre"
                    )
                
                # Risk flags if any
                if listing.scores.risk_assessment.flags:
                    flag_texts = [listing.scores.risk_assessment.explanations.get(f.value, f.value) 
                                  for f in listing.scores.risk_assessment.flags]
                    st.warning("⚠️ " + " | ".join(flag_texts[:2]))
                
                # Extracted attributes
                with st.expander("📋 Extraherade attribut"):
                    attr_col1, attr_col2 = st.columns(2)
                    attrs = listing.attributes
                    with attr_col1:
                        st.write(f"**Modell:** {attrs.model_variant or '❓'}")
                        st.write(f"**Lagring:** {attrs.storage_gb} GB" if attrs.storage_gb else "**Lagring:** ❓")
                        st.write(f"**Skick:** {attrs.condition.value}")
                        st.write(f"**Batteri:** {attrs.battery_health}%" if attrs.battery_health else "**Batteri:** ❓")
                    with attr_col2:
                        st.write(f"**Sprickor:** {'Ja ⚠️' if attrs.has_cracks else 'Nej ✅' if attrs.has_cracks is False else '❓'}")
                        st.write(f"**Garanti:** {'Ja ✅' if attrs.has_warranty else 'Nej' if attrs.has_warranty is False else '❓'}")
                        st.write(f"**Kvitto:** {'Ja ✅' if attrs.has_receipt else 'Nej' if attrs.has_receipt is False else '❓'}")
                        st.write(f"**Olåst:** {'Ja ✅' if attrs.is_locked is False else 'Nej ⚠️' if attrs.is_locked else '❓'}")
                
                # Checklist
                if listing.checklist:
                    st.info("📝 **Fråga säljaren:** " + ", ".join(listing.checklist[:3]))
                
                st.markdown("---")

        # Export evaluation results
        st.subheader("📥 Exportera")
        if st.button("Exportera evaluering som JSON"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"evaluation_{eval_query.replace(' ', '_')[:20]}_{timestamp}.json"
            filepath = os.path.join(EXPORTS_DIR, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.model_dump(), f, indent=2, ensure_ascii=False, default=str)
            
            st.success(f"Exporterad till: {filepath}")


# === WATCHES PAGE ===
elif page == "👁️ Bevakningar":
    st.title("👁️ Bevakningar")

    tab1, tab2 = st.tabs(["📋 Mina bevakningar", "➕ Skapa ny"])

    # === TAB: LIST WATCHES ===
    with tab1:
        watches = get_watches()

        if not watches:
            st.info("Du har inga sparade bevakningar än. Skapa en ny i fliken ovan!")
        else:
            for watch in watches:
                with st.expander(f"🔔 {watch['name'] or watch['query']}", expanded=False):
                    st.markdown(f"**Query:** `{watch['query']}`")
                    st.markdown(f"**Skapad:** {watch['created_at']}")

                    if watch.get("filters"):
                        st.markdown("**Filter:**")
                        st.json(watch["filters"])

                    if watch.get("preferences"):
                        st.markdown("**Preferenser:**")
                        st.json(watch["preferences"])

                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        if st.button("▶️ Kör nu", key=f"run_{watch['id']}"):
                            st.session_state.current_watch_id = watch["id"]
                            filters = watch.get("filters", {})
                            with st.spinner("Söker..."):
                                try:
                                    raw_results = st.session_state.client.search(
                                        query=watch["query"],
                                        locations=filters.get("locations"),
                                        category=filters.get("category"),
                                        sort_order=filters.get("sort_order"),
                                    )
                                    normalized = normalize_listings(raw_results)
                                    st.session_state.watch_results = [l.model_dump() for l in normalized]
                                    st.success(f"Hittade {len(normalized)} annonser")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Fel: {str(e)}")

                    with col2:
                        if st.button("🗑️ Ta bort", key=f"del_{watch['id']}"):
                            delete_watch(watch["id"])
                            st.success("Bevakning borttagen")
                            st.rerun()

            # Show results for current watch
            if st.session_state.watch_results and st.session_state.current_watch_id:
                st.markdown("---")
                current_watch = get_watch(st.session_state.current_watch_id)
                if current_watch:
                    st.subheader(f"Resultat för: {current_watch['name'] or current_watch['query']}")

                    from storage import get_seen_listing_ids
                    seen_ids = get_seen_listing_ids(st.session_state.current_watch_id)
                    new_listings = filter_new_listings(
                        st.session_state.current_watch_id,
                        st.session_state.watch_results
                    )

                    st.info(f"📊 Totalt: {len(st.session_state.watch_results)} | Nya: {len(new_listings)} | Sedda: {len(st.session_state.watch_results) - len(new_listings)}")

                    render_results_table(
                        st.session_state.watch_results,
                        show_new_indicator=True,
                        seen_ids=seen_ids,
                    )

                    # Export buttons
                    col1, col2, col3, col4 = st.columns(4)

                    with col1:
                        if st.button("📥 Full export", type="secondary"):
                            filepath = export_to_json(
                                listings=st.session_state.watch_results,
                                query=current_watch["query"],
                                watch_id=current_watch["id"],
                                filters=Filters(**current_watch.get("filters", {})),
                                preferences=Preferences(**current_watch.get("preferences", {})),
                                mode="full",
                            )
                            # Mark all as seen
                            mark_listings_seen(current_watch["id"], st.session_state.watch_results)
                            st.success(f"Exporterad till: {filepath}")

                    with col2:
                        if st.button("📤 Delta export", type="secondary"):
                            filepath = export_to_json(
                                listings=new_listings,
                                query=current_watch["query"],
                                watch_id=current_watch["id"],
                                filters=Filters(**current_watch.get("filters", {})),
                                preferences=Preferences(**current_watch.get("preferences", {})),
                                mode="delta",
                            )
                            # Mark new as seen
                            mark_listings_seen(current_watch["id"], new_listings)
                            st.success(f"Exporterade {len(new_listings)} nya annonser till: {filepath}")

    # === TAB: CREATE WATCH ===
    with tab2:
        st.subheader("Skapa ny bevakning")

        with st.form("create_watch_form"):
            name = st.text_input(
                "Namn (valfritt)",
                placeholder="t.ex. Billiga iPhones i Stockholm",
            )

            query = st.text_input(
                "Sökord *",
                placeholder="t.ex. iPhone 15",
            )

            # Filters
            locations, category, sort_order = render_filters_form("watch_create_")

            st.markdown("---")

            # Preferences
            preferences = render_preferences_form("watch_create_")

            submitted = st.form_submit_button("💾 Spara bevakning", type="primary")

            if submitted:
                if not query:
                    st.error("Sökord är obligatoriskt!")
                else:
                    filters = Filters(
                        locations=locations,
                        category=category,
                        sort_order=sort_order,
                    )
                    watch_id = create_watch(
                        name=name if name else None,
                        query=query,
                        filters=filters,
                        preferences=preferences,
                    )
                    st.success(f"Bevakning skapad! ID: {watch_id}")
                    st.rerun()


# === ABOUT PAGE ===
elif page == "ℹ️ Om":
    st.title("ℹ️ Om Blocket Bot")

    st.markdown("""
    ## 🎯 Syfte

    Blocket Bot är en testpanel för att:
    - Söka efter annonser på Blocket
    - Spara och hantera bevakningar (saved searches)
    - Exportera resultat som normaliserad JSON för vidare bearbetning

    ## 🚀 Funktioner

    ### Sökning
    - Fri textsökning med valfria filter (plats, sortering)
    - Resultat visas i tabell med titel, pris, plats och länk
    - Export till JSON-fil

    ### Bevakningar
    - Spara sökningar med namn och preferenser
    - Kör bevakningar för att hämta aktuella annonser
    - Deduplicering: se vilka annonser som är nya sedan senaste körning
    - Full export (alla) eller Delta export (bara nya)

    ### Preferenser
    - Fyll i preferenser som ska användas vid framtida värdering
    - Preferenserna sparas och exporteras med resultaten
    - De påverkar inte sökningen än - detta är förberedelse för nästa steg

    ## 📁 Exportformat

    Exporterade JSON-filer sparas i `exports/` mappen och följer ett normaliserat schema:

    ```json
    {
      "metadata": {
        "exported_at": "ISO8601",
        "query": "sökord",
        "watch_id": "uuid eller null",
        "filters": {...},
        "preferences": {...},
        "mode": "full" | "delta"
      },
      "listings": [
        {
          "listing_id": "...",
          "url": "...",
          "title": "...",
          "price": {"amount": 1234, "currency": "SEK"},
          "location": "...",
          "published_at": "ISO8601",
          "shipping_available": true/false/null,
          "fetched_at": "ISO8601",
          "raw": {...}
        }
      ]
    }
    ```

    ## 🔧 Teknisk info

    - **Backend:** Python + BlocketAPI
    - **UI:** Streamlit
    - **Databas:** MySQL (bevakningar + deduplikering)
    - **Export:** JSON-filer i `exports/`
    """)

    st.markdown("---")
    st.caption("Blocket Bot v0.1.0 - Testpanel för Blocket-sökning")
