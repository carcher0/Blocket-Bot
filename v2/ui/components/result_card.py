"""
Result card component - displays ranked listings.
"""
import streamlit as st
from typing import Optional

from ...models.scoring import RankedListing


def render_results_section(results: list[RankedListing]):
    """
    Render the results section with listing cards.
    
    Args:
        results: List of ranked listings to display
    """
    if not results:
        st.info("Inga resultat att visa")
        return
    
    for result in results:
        render_result_card(result)


def render_result_card(result: RankedListing):
    """Render a single result card."""
    listing = result.listing
    scores = result.scores
    enrichment = result.enrichment
    
    # Determine score class
    score_class = "score-average"
    if scores.total >= 75:
        score_class = "score-excellent"
    elif scores.total >= 60:
        score_class = "score-good"
    elif scores.total < 40:
        score_class = "score-poor"
    
    # Build tags
    tags_html = ""
    if result.is_good_deal:
        tags_html += '<span class="tag tag-deal">🏷️ Bra pris</span>'
    if result.has_high_risk:
        tags_html += '<span class="tag tag-risk">⚠️ Risker</span>'
    if result.missing_critical_info:
        tags_html += '<span class="tag tag-missing">❓ Saknar info</span>'
    
    # Format price
    price_str = f"{listing.price:,.0f} kr" if listing.price else "Pris saknas"
    
    # Card HTML
    card_html = f"""
    <div class="result-card">
        <div class="card-header">
            <span class="rank">#{result.rank}</span>
            <span class="score-badge {score_class}">{scores.total:.0f} poäng</span>
        </div>
        <div class="title">{listing.title or 'Utan titel'}</div>
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="price">{price_str}</span>
            <span class="location">📍 {listing.location or 'Okänd plats'}</span>
        </div>
        <div style="margin-top: 0.5rem;">
            {tags_html}
        </div>
    </div>
    """
    
    st.markdown(card_html, unsafe_allow_html=True)
    
    # Expandable details
    with st.expander("📊 Detaljer", expanded=False):
        render_card_details(result)


def render_card_details(result: RankedListing):
    """Render the expanded details for a result card."""
    listing = result.listing
    scores = result.scores
    enrichment = result.enrichment
    market = result.market_stats
    
    # Score breakdown
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "Värde",
            f"{scores.value_score.score:.0f}",
            f"{scores.value_score.deal_delta_percent:+.0f}%" if scores.value_score.deal_delta_percent else None,
        )
    
    with col2:
        st.metric(
            "Preferensmatch",
            f"{scores.preference_score.score:.0f}",
        )
    
    with col3:
        st.metric(
            "Risk",
            f"{scores.risk_score.score:.0f}",
        )
    
    # Market comparison
    if market and market.is_sufficient:
        st.markdown("**📈 Marknadsjämförelse:**")
        st.markdown(f"""
        - Median: **{market.median:,.0f} kr** ({market.n} jämförbara)
        - Intervall: {market.q1:,.0f} - {market.q3:,.0f} kr
        """)
    
    # Extracted attributes
    if enrichment.extracted_attributes:
        st.markdown("**🔍 Extraherade attribut:**")
        attrs_text = ", ".join(
            f"{name}: {attr.value}"
            for name, attr in enrichment.extracted_attributes.items()
            if name != "trust_signals"
        )
        st.markdown(attrs_text or "*Inga attribut extraherade*")
    
    # Risk flags
    if enrichment.risk_flags:
        st.markdown("**⚠️ Riskflaggor:**")
        for flag in enrichment.risk_flags:
            st.markdown(f"- {flag.explanation}")
    
    # Seller questions
    if enrichment.seller_questions:
        st.markdown("**💬 Frågor att ställa säljaren:**")
        for q in enrichment.seller_questions:
            st.markdown(f"""
            <div class="seller-question">
                <div class="question-text">"{q.question}"</div>
            </div>
            """, unsafe_allow_html=True)
            # Copy button
            st.button(
                "📋 Kopiera",
                key=f"copy_{result.listing.listing_id}_{q.relates_to}",
                on_click=lambda text=q.question: st.toast(f"Kopierat: {text[:30]}..."),
            )
    
    # Link to original
    st.markdown(f"[🔗 Visa på Blocket]({listing.url})")
