"""
Search input component.
"""
import streamlit as st
from typing import Optional


def render_search_section() -> tuple[str, dict]:
    """
    Render the search input section.
    
    Returns:
        Tuple of (query, filters_dict)
    """
    # Main search input
    query = st.text_input(
        "Sök",
        placeholder="T.ex. 'iPhone 15 Pro', 'Cykel 26 tum', 'IKEA soffa'...",
        key="search_query",
        label_visibility="collapsed",
    )
    
    # Filters in columns
    with st.expander("📍 Filter (valfritt)", expanded=False):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            locations = st.multiselect(
                "Platser",
                options=[
                    "stockholm", "göteborg", "malmö", "uppsala", 
                    "skane", "vastra_gotaland", "ostergotland"
                ],
                format_func=lambda x: x.replace("_", " ").title(),
                key="filter_locations",
            )
        
        with col2:
            max_price = st.number_input(
                "Maxpris (kr)",
                min_value=0,
                value=0,
                step=500,
                key="filter_max_price",
            )
        
        with col3:
            sort_order = st.selectbox(
                "Sortering",
                options=["relevance", "price_asc", "price_desc", "published_desc"],
                format_func=lambda x: {
                    "relevance": "Relevans",
                    "price_asc": "Lägsta pris",
                    "price_desc": "Högsta pris",
                    "published_desc": "Senaste",
                }.get(x, x),
                key="filter_sort",
            )
    
    filters = {
        "locations": locations if locations else None,
        "sort_order": sort_order,
        "max_price": max_price if max_price > 0 else None,
    }
    
    return query, filters
