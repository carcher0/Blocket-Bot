"""
Result card component - displays ranked listings.
"""
import streamlit as st
from typing import Optional

from v2.models.scoring import RankedListing


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
    
    # Description preview (first 120 chars)
    desc_preview = ""
    if listing.description:
        desc_text = listing.description[:120]
        if len(listing.description) > 120:
            desc_text += "..."
        desc_preview = f'<div class="description-preview">{desc_text}</div>'
    
    # Card HTML
    card_html = f"""
    <div class="result-card">
        <div class="card-header">
            <span class="rank">#{result.rank}</span>
            <span class="score-badge {score_class}">{scores.total:.0f} poäng</span>
        </div>
        <a href="{listing.url}" target="_blank" class="title" style="text-decoration: none; color: inherit;">
            {listing.title or 'Utan titel'}
        </a>
        {desc_preview}
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 0.5rem;">
            <span class="price">{price_str}</span>
            <span class="location">📍 {listing.location or 'Okänd plats'}</span>
        </div>
        <div style="margin-top: 0.5rem;">
            {tags_html}
        </div>
        <a href="{listing.url}" target="_blank" style="color: var(--primary); font-size: 0.85rem;">🔗 Öppna på Blocket</a>
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
        for idx, q in enumerate(enrichment.seller_questions):
            # Use st.code for easy copy-paste
            st.code(q.question, language=None)
    
    # Link to original
    st.markdown(f"[🔗 Visa på Blocket]({listing.url})")
