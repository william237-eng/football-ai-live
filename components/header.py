import streamlit as st


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
