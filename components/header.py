import streamlit as st
import unicodedata
import re
from datetime import datetime
from typing import Dict, List
from utils.profile_manager import get_profile, photo_to_base64


# ── Dictionnaire d'abbréviations / synonymes de recherche ──────────────────
_ALIASES: Dict[str, str] = {
    # Pays
    "fra": "france", "fr": "france",
    "esp": "espagne", "spa": "espagne", "spain": "espagne",
    "eng": "angleterre", "uk": "angleterre", "england": "angleterre",
    "ger": "allemagne", "all": "allemagne", "germany": "allemagne",
    "ita": "italie", "italy": "italie",
    "por": "portugal",
    "bel": "belgique", "belgium": "belgique",
    "ned": "pays-bas", "hol": "pays-bas", "netherlands": "pays-bas",
    "bra": "bresil", "brazil": "bresil",
    "arg": "argentine", "argentina": "argentine",
    "usa": "etats-unis", "us": "etats-unis",
    "rus": "russie", "russia": "russie",
    "tur": "turquie", "turkey": "turquie",
    "gre": "grece", "greece": "grece",
    # Compétitions
    "ucl": "champions league", "ldc": "champions league", "cl": "champions league",
    "uel": "europa league", "el": "europa league",
    "uecl": "conference league",
    "pl": "premier league", "epl": "premier league",
    "liga": "la liga",
    "bun": "bundesliga", "bl": "bundesliga",
    "sa": "serie a",
    "l1": "ligue 1", "ligue1": "ligue 1",
    "l2": "ligue 2", "ligue2": "ligue 2",
    "mls": "major league soccer",
    "wc": "world cup", "cm": "coupe du monde",
}


def _normalize(text: str) -> str:
    """Normalise : minuscules + supprime accents."""
    text = text.lower().strip()
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def _expand_query(raw: str) -> List[str]:
    """
    Découpe la requête en termes normalisés.
    Chaque terme doit matcher (logique ET).
    Un terme avec alias génère un groupe OR [original, alias]
    stocké comme tuple — le filtre accepte si l'un des deux matche.
    """
    terms = re.split(r"[\s,;|]+", raw.strip())
    expanded = []
    for t in terms:
        t = _normalize(t)
        if not t:
            continue
        alias = _ALIASES.get(t)
        if alias:
            # Groupe OR : le terme ou son alias doit matcher
            expanded.append((t, alias))
        else:
            expanded.append(t)
    return expanded


def _match_score(field_value: str, terms: List[str]) -> int:
    """
    Retourne un score de correspondance pour un champ (0 = aucun match).
    +3 : correspondance exacte du terme dans le champ
    +2 : le terme commence un mot du champ
    +1 : le terme est contenu dans le champ
    """
    if not field_value:
        return 0
    norm = _normalize(field_value)
    words = re.split(r"[\s\-_./]+", norm)
    score = 0
    for t in terms:
        if norm == t:
            score += 3
        elif any(w == t for w in words):
            score += 3
        elif any(w.startswith(t) for w in words):
            score += 2
        elif t in norm:
            score += 1
        else:
            return -1  # terme absent → match impossible
    return score


def get_formatted_datetime():
    """Retourne la date et heure formatées"""
    now = datetime.now()
    # Format: Lundi 27 Mai 2026 | 19:35
    date_str = now.strftime("%A %d %B %Y")
    time_str = now.strftime("%H:%M")
    return date_str, time_str


def render_datetime_header():
    """Affiche la date et heure avec la photo de profil à droite"""
    date_str, time_str = get_formatted_datetime()

    username, photo = get_profile()
    initiale = username[0].upper() if username else "U"

    if photo:
        b64 = photo_to_base64(photo)
        avatar_html = (
            f"<img src='data:image/png;base64,{b64}' "
            f"style='width:40px;height:40px;border-radius:50%;"
            f"border:2px solid #00d4ff;object-fit:cover;flex-shrink:0;' />"
        )
    else:
        avatar_html = (
            f"<div style='width:40px;height:40px;border-radius:50%;"
            f"background:linear-gradient(135deg,#00d4ff,#7c3aed);"
            f"border:2px solid #00d4ff;display:flex;align-items:center;"
            f"justify-content:center;font-weight:800;font-size:16px;"
            f"color:#fff;flex-shrink:0;'>{initiale}</div>"
        )

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
            <div class="profile-section" title="{username}">
                {avatar_html}
                <span class="profile-name">{username}</span>
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
        .profile-section {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-left: auto;
        }}
        .profile-name {{
            font-size: 0.85rem;
            font-weight: 600;
            color: #e0e0e0;
            white-space: nowrap;
            max-width: 120px;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        @media (max-width: 768px) {{
            .datetime-container {{
                justify-content: center;
                padding: 8px 12px;
            }}
            .date-text {{ font-size: 0.8rem; }}
            .time-text {{ font-size: 1rem; }}
            .profile-name {{ display: none; }}
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
            .profile-section {{ margin-left: 0; }}
        }}
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
    col1, col2 = st.columns([3, 2])
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
        current_q = st.session_state.get("search_query", "")

        search_c, clear_c = st.columns([5, 1])
        with search_c:
            search_query = st.text_input(
                "🔍",
                placeholder="🔍  Équipe, ligue, pays, UCL, PL, fra…",
                value=current_q,
                key="search_input",
                label_visibility="collapsed",
            )
        with clear_c:
            if st.button("✕", key="clear_search_btn",
                         help="Effacer la recherche",
                         use_container_width=True,
                         disabled=not bool(current_q)):
                st.session_state.search_query = ""
                st.rerun()

        # Mise à jour session_state sans rerun intempestif
        new_q = search_query.strip()
        if new_q != current_q:
            st.session_state.search_query = new_q
            st.rerun()

        # Aide contextuelle sous la barre
        if current_q:
            st.markdown(
                f"<div style='font-size:0.72rem;color:#888;margin-top:2px;'>"
                f"🔎 Résultats pour <b>\"{current_q}\"</b> — "
                f"<span style='color:#aaa;'>multi-mots, accents ignorés, abbréviations (UCL, PL, fra…)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='font-size:0.70rem;color:#666;margin-top:2px;'>"
                "Exemples : <i>PSG</i> · <i>champions league</i> · <i>UCL</i> · <i>fra</i> · <i>PSG Lyon</i>"
                "</div>",
                unsafe_allow_html=True,
            )


def get_search_query() -> str:
    """Récupère la requête de recherche actuelle"""
    return st.session_state.get("search_query", "").strip().lower()


def clear_search():
    """Efface la recherche"""
    if "search_query" in st.session_state:
        st.session_state.search_query = ""
        st.rerun()


def matches_search_filter(match: dict, query: str) -> bool:
    """
    Filtre intelligent : insensible à la casse, aux accents,
    multi-termes (ET logique), abbréviations, correspondance partielle.
    """
    if not query or not query.strip():
        return True

    terms = _expand_query(query)
    if not terms:
        return True

    # Champs avec priorité (les plus importants en premier)
    field_groups = [
        # Équipes — haute priorité
        match.get("home_team", ""),
        match.get("away_team", ""),
        # Compétition
        match.get("league", ""),
        # Pays
        match.get("league_country", ""),
        # Stade / ville
        match.get("venue", ""),
        match.get("city", ""),
        # Statut
        match.get("status_short", ""),
        # Combiné équipes (permet "psg lyon" de matcher directement)
        f"{match.get('home_team', '')} {match.get('away_team', '')}",
    ]

    # Chaque terme (ou groupe OR) doit matcher dans au moins un champ
    for term in terms:
        # term peut être un str simple ou un tuple (original, alias)
        candidates = term if isinstance(term, tuple) else (term,)
        term_matched = False
        for field in field_groups:
            if not field:
                continue
            norm = _normalize(str(field))
            if any(c in norm for c in candidates):
                term_matched = True
                break
        if not term_matched:
            return False

    return True


def matches_search_score(match: dict, query: str) -> int:
    """Retourne un score de pertinence pour le tri (plus élevé = plus pertinent)."""
    if not query or not query.strip():
        return 0
    terms = _expand_query(query)
    if not terms:
        return 0

    scored_fields = [
        (match.get("home_team", ""),      4),
        (match.get("away_team", ""),       4),
        (match.get("league", ""),          3),
        (match.get("league_country", ""),  2),
        (match.get("venue", ""),           1),
    ]
    total = 0
    for field_val, weight in scored_fields:
        norm = _normalize(str(field_val))
        words = re.split(r"[\s\-_./]+", norm)
        field_score = 0
        for term in terms:
            candidates = term if isinstance(term, tuple) else (term,)
            best = 0
            for c in candidates:
                if norm == c:
                    best = max(best, 3)
                elif any(w == c for w in words):
                    best = max(best, 3)
                elif any(w.startswith(c) for w in words):
                    best = max(best, 2)
                elif c in norm:
                    best = max(best, 1)
            field_score += best
        if field_score > 0:
            total += field_score * weight
    return total
