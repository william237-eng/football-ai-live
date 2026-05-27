"""
Theme Manager - Gestion des thèmes dynamiques premium
"""
from typing import Dict, Any
import streamlit as st


# Définition des thèmes premium
THEMES = {
    "dark_pro": {
        "name": "Dark Pro",
        "icon": "🌙",
        "colors": {
            "background_primary": "#0a0a0f",
            "background_secondary": "#12121a",
            "background_card": "#1a1a24",
            "background_hover": "#252532",
            "background_gradient_start": "#0f1419",
            "background_gradient_end": "#1a1f2e",
            "text_primary": "#ffffff",
            "text_secondary": "#a0a0b0",
            "text_muted": "#6a6a7a",
            "border": "#2a2a3a",
            "border_highlight": "#3a3a4f",
            "accent_primary": "#00d4ff",
            "accent_secondary": "#7c3aed",
            "accent_success": "#00ff88",
            "accent_warning": "#ffb800",
            "accent_danger": "#ff4757",
            "accent_info": "#2d95f5",
            "shadow": "rgba(0, 0, 0, 0.4)",
            "glass": "rgba(26, 26, 36, 0.85)",
            "live": "#ff4757",
            "fixture": "#ffb800",
            "finished": "#00ff88",
        },
        "chart": {
            "home_color": "#00d4ff",
            "away_color": "#ff6b6b",
            "grid_color": "#2a2a3a",
            "text_color": "#a0a0b0",
        }
    },
    "light_pro": {
        "name": "Light Pro",
        "icon": "☀️",
        "colors": {
            "background_primary": "#fafafa",
            "background_secondary": "#f5f5f7",
            "background_card": "#ffffff",
            "background_hover": "#f0f0f5",
            "background_gradient_start": "#f8f9fa",
            "background_gradient_end": "#e9ecef",
            "text_primary": "#1a1a2e",
            "text_secondary": "#4a4a5a",
            "text_muted": "#6a6a7a",
            "border": "#e0e0e5",
            "border_highlight": "#d0d0d8",
            "accent_primary": "#0066cc",
            "accent_secondary": "#7c3aed",
            "accent_success": "#28a745",
            "accent_warning": "#f59e0b",
            "accent_danger": "#dc2626",
            "accent_info": "#0891b2",
            "shadow": "rgba(0, 0, 0, 0.08)",
            "glass": "rgba(255, 255, 255, 0.9)",
            "live": "#dc2626",
            "fixture": "#f59e0b",
            "finished": "#28a745",
        },
        "chart": {
            "home_color": "#0066cc",
            "away_color": "#dc2626",
            "grid_color": "#e0e0e5",
            "text_color": "#4a4a5a",
        }
    },
    "blue_sky": {
        "name": "Blue Sky",
        "icon": "🌤️",
        "colors": {
            "background_primary": "#f0f7ff",
            "background_secondary": "#e6f0fa",
            "background_card": "#ffffff",
            "background_hover": "#dbeafe",
            "background_gradient_start": "#e0f2fe",
            "background_gradient_end": "#f0f9ff",
            "text_primary": "#0f172a",
            "text_secondary": "#334155",
            "text_muted": "#64748b",
            "border": "#bfdbfe",
            "border_highlight": "#93c5fd",
            "accent_primary": "#0369a1",
            "accent_secondary": "#7c3aed",
            "accent_success": "#059669",
            "accent_warning": "#d97706",
            "accent_danger": "#dc2626",
            "accent_info": "#0284c7",
            "shadow": "rgba(14, 165, 233, 0.1)",
            "glass": "rgba(255, 255, 255, 0.92)",
            "live": "#dc2626",
            "fixture": "#d97706",
            "finished": "#059669",
        },
        "chart": {
            "home_color": "#0369a1",
            "away_color": "#dc2626",
            "grid_color": "#bfdbfe",
            "text_color": "#334155",
        }
    }
}


def get_current_theme() -> str:
    """Récupère le thème actuel depuis session_state"""
    return st.session_state.get("theme", "dark_pro")


def set_theme(theme_name: str) -> None:
    """Change le thème et stocke dans session_state"""
    if theme_name in THEMES:
        st.session_state.theme = theme_name


def get_theme_colors(theme_name: str = None) -> Dict[str, str]:
    """Retourne les couleurs du thème spécifié"""
    if theme_name is None:
        theme_name = get_current_theme()
    return THEMES.get(theme_name, THEMES["dark_pro"])["colors"]


def get_theme_config(theme_name: str = None) -> Dict[str, Any]:
    """Retourne la configuration complète du thème"""
    if theme_name is None:
        theme_name = get_current_theme()
    return THEMES.get(theme_name, THEMES["dark_pro"])


def get_chart_colors(theme_name: str = None) -> Dict[str, str]:
    """Retourne les couleurs pour les graphiques"""
    if theme_name is None:
        theme_name = get_current_theme()
    return THEMES.get(theme_name, THEMES["dark_pro"])["chart"]


def generate_css_variables(theme_name: str = None) -> str:
    """Génère les variables CSS pour le thème"""
    colors = get_theme_colors(theme_name)
    css_vars = []
    for key, value in colors.items():
        css_vars.append(f"  --{key}: {value};")
    return "\n".join(css_vars)


def get_theme_css(theme_name: str = None) -> str:
    """Génère le CSS complet pour le thème"""
    if theme_name is None:
        theme_name = get_current_theme()
    
    colors = get_theme_colors(theme_name)
    is_dark = theme_name == "dark_pro"
    
    return f"""
:root {{
  --bg-primary: {colors['background_primary']};
  --bg-secondary: {colors['background_secondary']};
  --bg-card: {colors['background_card']};
  --bg-hover: {colors['background_hover']};
  --bg-gradient-start: {colors['background_gradient_start']};
  --bg-gradient-end: {colors['background_gradient_end']};
  --text-primary: {colors['text_primary']};
  --text-secondary: {colors['text_secondary']};
  --text-muted: {colors['text_muted']};
  --border: {colors['border']};
  --border-highlight: {colors['border_highlight']};
  --accent-primary: {colors['accent_primary']};
  --accent-secondary: {colors['accent_secondary']};
  --accent-success: {colors['accent_success']};
  --accent-warning: {colors['accent_warning']};
  --accent-danger: {colors['accent_danger']};
  --accent-info: {colors['accent_info']};
  --shadow: {colors['shadow']};
  --glass: {colors['glass']};
  --live: {colors['live']};
  --fixture: {colors['fixture']};
  --finished: {colors['finished']};
}}

/* ===== BASE STYLES ===== */
.stApp {{
  background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
  color: var(--text-primary);
}}

/* Main content area */
.main .block-container {{
  background: transparent;
  padding: 2rem;
}}

/* Typography */
h1, h2, h3, h4, h5, h6 {{
  color: var(--text-primary) !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  font-weight: 700;
  letter-spacing: -0.02em;
}}

p, span, div {{
  color: var(--text-secondary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}}

/* ===== GLASSMORPHISM CARDS ===== */
.glass-card {{
  background: var(--glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-highlight);
  border-radius: 16px;
  box-shadow: 0 8px 32px var(--shadow);
  padding: 24px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}}

.glass-card:hover {{
  transform: translateY(-4px);
  box-shadow: 0 12px 40px var(--shadow);
  border-color: var(--accent-primary);
}}

/* ===== MATCH CARDS ===== */
.match-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 4px 20px var(--shadow);
  transition: all 0.3s ease;
}}

.match-card:hover {{
  border-color: var(--accent-primary);
  transform: translateY(-2px);
  box-shadow: 0 8px 30px var(--shadow);
}}

/* Status badges */
.status-live {{
  background: linear-gradient(135deg, var(--accent-danger), #ff6b6b);
  color: white;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
  animation: pulse 2s infinite;
}}

.status-fixture {{
  background: var(--accent-warning);
  color: {'#1a1a2e' if not is_dark else 'white'};
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}}

.status-finished {{
  background: var(--accent-success);
  color: {'#1a1a2e' if not is_dark else 'white'};
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 600;
}}

@keyframes pulse {{
  0%, 100% {{ opacity: 1; }}
  50% {{ opacity: 0.7; }}
}}

/* ===== SIDEBAR STYLES ===== */
[data-testid="stSidebar"] {{
  background: var(--bg-secondary);
  border-right: 1px solid var(--border);
}}

[data-testid="stSidebar"] .sidebar-content {{
  padding: 20px;
}}

[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {{
  color: var(--text-primary) !important;
}}

[data-testid="stSidebar"] .stRadio label {{
  color: var(--text-secondary) !important;
}}

[data-testid="stSidebar"] .stSelectbox label {{
  color: var(--text-secondary) !important;
}}

/* Sidebar buttons */
.sidebar-button {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 12px 16px;
  border-radius: 12px;
  width: 100%;
  transition: all 0.2s ease;
  cursor: pointer;
}}

.sidebar-button:hover {{
  background: var(--bg-hover);
  border-color: var(--accent-primary);
  color: var(--text-primary);
}}

.sidebar-button.active {{
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
  color: white;
  border-color: transparent;
}}

/* ===== BUTTONS ===== */
.stButton > button {{
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
  color: white;
  border: none;
  border-radius: 12px;
  padding: 12px 24px;
  font-weight: 600;
  transition: all 0.3s ease;
  box-shadow: 0 4px 15px {colors['accent_primary']}40;
}}

.stButton > button:hover {{
  transform: translateY(-2px);
  box-shadow: 0 6px 20px {colors['accent_primary']}60;
}}

.stButton > button:active {{
  transform: translateY(0);
}}

/* Secondary button */
.stButton > button[kind="secondary"] {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  box-shadow: none;
}}

.stButton > button[kind="secondary"]:hover {{
  background: var(--bg-hover);
  border-color: var(--accent-primary);
  color: var(--text-primary);
}}

/* ===== METRICS & STATS ===== */
[data-testid="stMetricValue"] {{
  color: var(--text-primary) !important;
  font-size: 2rem;
  font-weight: 700;
}}

[data-testid="stMetricLabel"] {{
  color: var(--text-secondary) !important;
  font-size: 0.875rem;
}}

[data-testid="stMetricDelta"] {{
  color: var(--accent-success) !important;
}}

/* Progress bars */
.stProgress > div > div {{
  background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
  border-radius: 10px;
}}

.stProgress {{
  background: var(--bg-hover);
  border-radius: 10px;
}}

/* ===== INPUTS ===== */
.stTextInput > div > div > input {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 12px;
  padding: 12px 16px;
}}

.stTextInput > div > div > input:focus {{
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px {colors['accent_primary']}20;
}}

.stSelectbox > div > div > select {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-primary);
  border-radius: 12px;
}}

/* ===== TABS ===== */
.stTabs [data-baseweb="tab-list"] {{
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 4px;
}}

.stTabs [data-baseweb="tab"] {{
  color: var(--text-secondary);
  border-radius: 8px;
  padding: 12px 24px;
  transition: all 0.2s ease;
}}

.stTabs [aria-selected="true"] {{
  background: var(--bg-card);
  color: var(--text-primary);
  box-shadow: 0 2px 8px var(--shadow);
}}

/* ===== ANALYSIS DASHBOARD ===== */
.analysis-shell {{
  background: var(--bg-card);
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 4px 24px var(--shadow);
}}

.analysis-hero {{
  background: linear-gradient(135deg, var(--bg-gradient-start), var(--bg-gradient-end));
  border-radius: 16px;
  padding: 32px;
  text-align: center;
  border: 1px solid var(--border);
}}

.analysis-team h2 {{
  color: var(--text-primary);
  font-size: 1.5rem;
  margin: 12px 0;
}}

.analysis-score {{
  background: var(--glass);
  backdrop-filter: blur(10px);
  border: 1px solid var(--border-highlight);
  border-radius: 20px;
  padding: 24px 40px;
}}

.analysis-score div {{
  font-size: 3rem;
  font-weight: 800;
  color: var(--text-primary);
}}

.analysis-meta {{
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-top: 16px;
}}

.analysis-card {{
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
}}

/* ===== BET SUGGESTIONS ===== */
.bet-suggestion {{
  background: linear-gradient(135deg, var(--glass), var(--bg-secondary));
  border: 1px solid var(--border);
  border-left: 4px solid var(--accent-primary);
  border-radius: 12px;
  padding: 20px;
  margin: 12px 0;
  transition: all 0.3s ease;
}}

.bet-suggestion:hover {{
  border-color: var(--accent-primary);
  transform: translateX(4px);
}}

.bet-suggestion.high-confidence {{
  border-left-color: var(--accent-success);
}}

.bet-suggestion.medium-confidence {{
  border-left-color: var(--accent-warning);
}}

.bet-suggestion.low-confidence {{
  border-left-color: var(--accent-danger);
}}

/* ===== CONFIDENCE LEVELS ===== */
.confidence-very-high {{
  color: var(--accent-success);
}}

.confidence-high {{
  color: #22c55e;
}}

.confidence-medium {{
  color: var(--accent-warning);
}}

.confidence-low {{
  color: var(--accent-danger);
}}

/* ===== TABLES ===== */
.stDataFrame {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
}}

.stDataFrame th {{
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-weight: 600;
}}

.stDataFrame td {{
  color: var(--text-secondary);
}}

/* ===== EXPANDERS ===== */
.streamlit-expanderHeader {{
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--text-primary);
}}

.streamlit-expanderContent {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-top: none;
  border-radius: 0 0 12px 12px;
}}

/* ===== SCROLLBAR ===== */
::-webkit-scrollbar {{
  width: 8px;
  height: 8px;
}}

::-webkit-scrollbar-track {{
  background: var(--bg-secondary);
  border-radius: 4px;
}}

::-webkit-scrollbar-thumb {{
  background: var(--border-highlight);
  border-radius: 4px;
}}

::-webkit-scrollbar-thumb:hover {{
  background: var(--accent-primary);
}}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {{
  .main .block-container {{
    padding: 1rem;
  }}
  
  .glass-card {{
    padding: 16px;
  }}
  
  .match-card {{
    padding: 16px;
  }}
  
  h1 {{ font-size: 1.5rem; }}
  h2 {{ font-size: 1.25rem; }}
  h3 {{ font-size: 1.1rem; }}
  
  .analysis-score div {{
    font-size: 2rem;
  }}
  
  .analysis-team h2 {{
    font-size: 1.1rem;
  }}
}}

@media (min-width: 1920px) {{
  .main .block-container {{
    max-width: 1600px;
    padding: 3rem;
  }}
  
  .glass-card {{
    padding: 32px;
  }}
}}

/* ===== ANIMATIONS ===== */
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(20px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.animate-in {{
  animation: fadeIn 0.5s ease-out;
}}

/* ===== LOADING ===== */
.stSpinner > div {{
  border-color: var(--accent-primary) transparent transparent transparent;
}}

/* ===== DIVIDERS ===== */
hr {{
  border: none;
  border-top: 1px solid var(--border);
  margin: 24px 0;
}}

/* ===== CAPTIONS ===== */
.stCaption {{
  color: var(--text-muted) !important;
  font-size: 0.75rem;
}}

/* ===== ALERTS ===== */
.stAlert {{
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
}}

.stSuccess {{
  border-left: 4px solid var(--accent-success);
}}

.stWarning {{
  border-left: 4px solid var(--accent-warning);
}}

.stError {{
  border-left: 4px solid var(--accent-danger);
}}

.stInfo {{
  border-left: 4px solid var(--accent-info);
}}
"""


def get_theme_selector() -> str:
    """Retourne le HTML pour le selecteur de thème"""
    current = get_current_theme()
    
    options_html = ""
    for key, theme in THEMES.items():
        is_active = "active" if key == current else ""
        options_html += f"""
        <div class="theme-option {is_active}" onclick="setTheme('{key}')">
            <span class="theme-icon">{theme['icon']}</span>
            <span class="theme-name">{theme['name']}</span>
        </div>
        """
    
    return f"""
    <div class="theme-selector">
        <div class="theme-label">🎨 Theme</div>
        {options_html}
    </div>
    <style>
    .theme-selector {{
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 12px;
        margin: 12px 0;
    }}
    .theme-label {{
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text-secondary);
        margin-bottom: 8px;
    }}
    .theme-option {{
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 12px;
        border-radius: 8px;
        cursor: pointer;
        transition: all 0.2s ease;
        color: var(--text-secondary);
    }}
    .theme-option:hover {{
        background: var(--bg-hover);
        color: var(--text-primary);
    }}
    .theme-option.active {{
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
        color: white;
    }}
    .theme-icon {{
        font-size: 1.25rem;
    }}
    .theme-name {{
        font-size: 0.875rem;
        font-weight: 500;
    }}
    </style>
    """
