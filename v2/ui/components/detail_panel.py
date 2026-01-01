"""
Detail panel component - full listing detail view.
"""
import streamlit as st
from typing import Optional

from ...models.scoring import RankedListing


def render_detail_panel(result: Optional[RankedListing]):
    """
    Render a full detail panel for a selected listing.
    
    Args:
        result: The ranked listing to show details for
    """
    if result is None:
        st.info("Välj en annons för att se detaljer")
        return
    
    listing = result.listing
    scores = result.scores
    enrichment = result.enrichment
    market = result.market_stats
    
    # Header
    st.markdown(f"## {listing.title}")
    st.markdown(f"**{listing.price:,.0f} kr** • 📍 {listing.location}")
    
    # Score overview
    st.markdown("### 📊 Poängsammanfattning")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total", f"{scores.total:.0f}/100")
    col2.metric("Värde", f"{scores.value_score.score:.0f}")
    col3.metric("Match", f"{scores.preference_score.score:.0f}")
    col4.metric("Risk", f"{scores.risk_score.score:.0f}")
    
    st.markdown(f"*{scores.summary_explanation}*")
    
    # Value analysis
    st.markdown("### 💰 Värdeanalys")
    if market and market.is_sufficient:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            - **Begärt pris:** {listing.price:,.0f} kr
            - **Marknadens median:** {market.median:,.0f} kr
            - **Delta:** {scores.value_score.deal_delta:+,.0f} kr ({scores.value_score.deal_delta_percent:+.1f}%)
            """)
        with col2:
            st.markdown(f"""
            - **Prisintervall (IQR):** {market.q1:,.0f} - {market.q3:,.0f} kr
            - **Jämförbara annonser:** {market.n}
            - **Relaxeringsnivå:** {market.relaxation_level}
            """)
    else:
        st.warning("Otillräckliga jämförelseobjekt för prisanalys")
    
    # Attributes
    st.markdown("### 🔍 Extraherade attribut")
    if enrichment.extracted_attributes:
        for name, attr in enrichment.extracted_attributes.items():
            if name == "trust_signals":
                continue
            confidence_bar = "🟢" if attr.confidence > 0.8 else "🟡" if attr.confidence > 0.5 else "🔴"
            st.markdown(f"- **{name}:** {attr.value} {confidence_bar} ({attr.confidence*100:.0f}%)")
    else:
        st.markdown("*Inga attribut extraherade*")
    
    # Missing info
    if enrichment.missing_fields:
        st.markdown("### ❓ Saknad information")
        for field in enrichment.missing_fields:
            st.markdown(f"- {field}")
    
    # Risk assessment
    st.markdown("### ⚠️ Riskbedömning")
    if enrichment.risk_flags:
        for flag in enrichment.risk_flags:
            severity_icon = "🔴" if flag.severity > 0.7 else "🟡" if flag.severity > 0.4 else "🟢"
            st.markdown(f"{severity_icon} **{flag.flag_type}:** {flag.explanation}")
    else:
        st.success("Inga riskflaggor upptäckta ✓")
    
    # Seller questions
    st.markdown("### 💬 Frågor till säljaren")
    if enrichment.seller_questions:
        for q in enrichment.seller_questions:
            with st.container():
                st.markdown(f"""
                <div class="seller-question">
                    <div class="question-text">"{q.question}"</div>
                    <small style="color: var(--text-muted);">Anledning: {q.reason}</small>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.markdown("*Inga frågor genererade*")
    
    # Link
    st.markdown("---")
    st.markdown(f"[🔗 Öppna annons på Blocket]({listing.url})")
