"""
Custom CSS styles for Blocket Bot 2.0.
Blocket-inspired premium dark theme.
"""
import streamlit as st


# Color palette (Blocket-inspired)
COLORS = {
    "primary": "#0077B5",      # Blocket blue
    "primary_hover": "#005A8C",
    "accent": "#FFD200",       # Blocket yellow
    "accent_dark": "#E6BD00",
    "background": "#0D1117",   # Dark background
    "surface": "#161B22",      # Card background
    "surface_hover": "#1F2937",
    "text": "#E6EDF3",         # Light text
    "text_muted": "#8B949E",
    "success": "#2EA043",
    "warning": "#D29922",
    "error": "#F85149",
    "border": "#30363D",
}


def inject_custom_css():
    """Inject custom CSS into the Streamlit app."""
    st.markdown(f"""
    <style>
    /* Import Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Root variables */
    :root {{
        --primary: {COLORS['primary']};
        --primary-hover: {COLORS['primary_hover']};
        --accent: {COLORS['accent']};
        --accent-dark: {COLORS['accent_dark']};
        --bg: {COLORS['background']};
        --surface: {COLORS['surface']};
        --surface-hover: {COLORS['surface_hover']};
        --text: {COLORS['text']};
        --text-muted: {COLORS['text_muted']};
        --success: {COLORS['success']};
        --warning: {COLORS['warning']};
        --error: {COLORS['error']};
        --border: {COLORS['border']};
    }}
    
    /* Global styles */
    .stApp {{
        font-family: 'Inter', -apple-system, sans-serif;
        background: linear-gradient(180deg, var(--bg) 0%, #161B22 100%);
    }}
    
    /* Header */
    .app-header {{
        text-align: center;
        padding: 2rem 0 1rem;
    }}
    
    .app-header h1 {{
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(135deg, var(--primary) 0%, var(--accent) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }}
    
    .app-header .subtitle {{
        color: var(--text-muted);
        font-size: 1.1rem;
        font-weight: 400;
    }}
    
    /* Cards */
    .result-card {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
    }}
    
    .result-card:hover {{
        background: var(--surface-hover);
        border-color: var(--primary);
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(0, 119, 181, 0.15);
    }}
    
    .result-card .card-header {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 0.75rem;
    }}
    
    .result-card .rank {{
        font-size: 1.5rem;
        font-weight: 700;
        color: var(--accent);
    }}
    
    .result-card .title {{
        font-size: 1.1rem;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 0.5rem;
    }}
    
    .result-card .price {{
        font-size: 1.3rem;
        font-weight: 700;
        color: var(--accent);
    }}
    
    .result-card .location {{
        color: var(--text-muted);
        font-size: 0.9rem;
    }}
    
    .result-card .description-preview {{
        color: var(--text-muted);
        font-size: 0.85rem;
        margin: 0.5rem 0;
        line-height: 1.4;
    }}
    
    /* Score badges */
    .score-badge {{
        display: inline-flex;
        align-items: center;
        padding: 0.35rem 0.75rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.9rem;
    }}
    
    .score-excellent {{
        background: linear-gradient(135deg, #2EA043 0%, #3FB950 100%);
        color: white;
    }}
    
    .score-good {{
        background: linear-gradient(135deg, #D29922 0%, #F0B429 100%);
        color: #1a1a2e;
    }}
    
    .score-average {{
        background: var(--surface-hover);
        color: var(--text);
        border: 1px solid var(--border);
    }}
    
    .score-poor {{
        background: linear-gradient(135deg, #F85149 0%, #FF6B6B 100%);
        color: white;
    }}
    
    /* Tags */
    .tag {{
        display: inline-block;
        padding: 0.25rem 0.5rem;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 500;
        margin-right: 0.5rem;
        margin-bottom: 0.25rem;
    }}
    
    .tag-deal {{
        background: rgba(46, 160, 67, 0.2);
        color: var(--success);
        border: 1px solid var(--success);
    }}
    
    .tag-risk {{
        background: rgba(248, 81, 73, 0.2);
        color: var(--error);
        border: 1px solid var(--error);
    }}
    
    .tag-missing {{
        background: rgba(210, 153, 34, 0.2);
        color: var(--warning);
        border: 1px solid var(--warning);
    }}
    
    /* Domain badge */
    .domain-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.5rem 1rem;
        margin-bottom: 1rem;
    }}
    
    .domain-badge .domain-label {{
        font-weight: 600;
        color: var(--primary);
    }}
    
    .domain-badge .confidence {{
        color: var(--text-muted);
        font-size: 0.85rem;
    }}
    
    /* Form inputs */
    .stTextInput input, .stSelectbox select {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        color: var(--text) !important;
    }}
    
    .stTextInput input:focus {{
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 2px rgba(0, 119, 181, 0.2) !important;
    }}
    
    /* Primary button */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, var(--primary) 0%, #005A8C 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.75rem 1.5rem !important;
        transition: all 0.2s ease !important;
    }}
    
    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(0, 119, 181, 0.4) !important;
    }}
    
    /* Secondary button */
    .stButton > button:not([kind="primary"]) {{
        background: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }}
    
    /* Metrics */
    [data-testid="stMetric"] {{
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 1rem;
    }}
    
    [data-testid="stMetricValue"] {{
        color: var(--accent) !important;
    }}
    
    /* Expander */
    .streamlit-expanderHeader {{
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    
    /* Seller questions */
    .seller-question {{
        background: rgba(0, 119, 181, 0.1);
        border-left: 3px solid var(--primary);
        padding: 0.75rem 1rem;
        margin-bottom: 0.5rem;
        border-radius: 0 8px 8px 0;
    }}
    
    .seller-question .question-text {{
        color: var(--text);
        font-style: italic;
    }}
    
    /* Progress indicator */
    .step-indicator {{
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-bottom: 2rem;
    }}
    
    .step {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: var(--text-muted);
    }}
    
    .step.active {{
        color: var(--primary);
    }}
    
    .step.completed {{
        color: var(--success);
    }}
    
    .step-number {{
        width: 28px;
        height: 28px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 0.85rem;
        border: 2px solid currentColor;
    }}
    
    .step.active .step-number {{
        background: var(--primary);
        color: white;
        border-color: var(--primary);
    }}
    
    .step.completed .step-number {{
        background: var(--success);
        color: white;
        border-color: var(--success);
    }}
    </style>
    """, unsafe_allow_html=True)
