import streamlit as st
from datetime import datetime


def get_formatted_datetime():
    """Retourne la date et heure formatées"""
    now = datetime.now()
    # Format: Lundi 27 Mai 2026 | 19:35
    date_str = now.strftime("%A %d %B %Y")
    time_str = now.strftime("%H:%M")
    return date_str, time_str


def render_datetime_header():
    """Affiche la date et heure au-dessus du logo - design responsive"""
    date_str, time_str = get_formatted_datetime()
    
    # HTML/CSS responsive pour la date/heure
    datetime_html = f"""
    <div class="datetime-header">
        <div class="datetime-container">
            <div class="date-section">
                <span class="calendar-icon">📅</span>
                <span class="date-text">{date_str}</span>
            </div>
            <div class="time-section">
                <span class="clock-icon">🕐</span>
                <span class="time-text">{time_str}</span>
            </div>
        </div>
    </div>
    <style>
        .datetime-header {{
            width: 100%;
            margin-bottom: 12px;
            padding: 8px 0;
        }}
        .datetime-container {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
            background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 212, 255, 0.05) 100%);
            border: 1px solid rgba(0, 212, 255, 0.2);
            border-radius: 12px;
            padding: 10px 16px;
            backdrop-filter: blur(10px);
        }}
        .date-section, .time-section {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .calendar-icon, .clock-icon {{
            font-size: 1.1rem;
            filter: drop-shadow(0 0 4px rgba(0, 212, 255, 0.5));
        }}
        .date-text {{
            font-size: 0.9rem;
            font-weight: 500;
            color: #e0e0e0;
            text-transform: capitalize;
        }}
        .time-text {{
            font-size: 1.2rem;
            font-weight: 700;
            color: #00d4ff;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
            letter-spacing: 1px;
        }}
        /* Responsive */
        @media (max-width: 768px) {{
            .datetime-container {{
                justify-content: center;
                padding: 8px 12px;
            }}
            .date-text {{
                font-size: 0.8rem;
            }}
            .time-text {{
                font-size: 1rem;
            }}
        }}
        @media (max-width: 480px) {{
            .datetime-container {{
                flex-direction: column;
                gap: 6px;
                padding: 8px;
            }}
            .date-section, .time-section {{
                width: 100%;
                justify-content: center;
            }}
        }}
        /* Animation pulse sur l'heure */
        @keyframes time-pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.8; }}
        }}
        .time-section {{
            animation: time-pulse 2s ease-in-out infinite;
        }}
    </style>
    """
    st.markdown(datetime_html, unsafe_allow_html=True)


def render_header(page: str = "live"):
    col1, col2 = st.columns([3, 1])
    with col1:
        if page == "future":
            st.markdown(
                "<div class='header-left'><h2 class='title'>MATCHS FUTURS <span class='upcoming-badge'>UPCOMING</span></h2></div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div class='header-left'><h2 class='title'>MATCHS EN DIRECT <span class='live-badge'>LIVE</span></h2></div>",
                unsafe_allow_html=True,
            )

    with col2:
        # Barre de recherche fonctionnelle avec Streamlit
        search_query = st.text_input(
            "🔍 Rechercher",
            placeholder="Équipe, compétition...",
            value=st.session_state.get("search_query", ""),
            key="search_input",
            label_visibility="collapsed",
        )
        # Stocker la recherche dans session_state pour filtrer les matchs
        if search_query != st.session_state.get("search_query", ""):
            st.session_state.search_query = search_query.strip().lower()
            st.rerun()


def get_search_query() -> str:
    """Récupère la requête de recherche actuelle"""
    return st.session_state.get("search_query", "").strip().lower()


def clear_search():
    """Efface la recherche"""
    if "search_query" in st.session_state:
        st.session_state.search_query = ""
        st.rerun()


def matches_search_filter(match: dict, query: str) -> bool:
    """Filtre un match selon la recherche"""
    if not query:
        return True
    
    # Champs à rechercher
    search_fields = [
        match.get("home_team", ""),
        match.get("away_team", ""),
        match.get("league", ""),
        match.get("league_country", ""),
        match.get("venue", ""),
    ]
    
    # Recherche dans tous les champs
    for field in search_fields:
        if field and query in str(field).lower():
            return True
    
    return False
