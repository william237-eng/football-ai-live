import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from components import sidebar, header
from components.header import get_search_query, matches_search_filter
from components.analysis_dashboard import render_analysis_dashboard
from services.football_api import FootballAPI, ConfigError, APIError, RateLimitError, NetworkError
from services.live_matches import LiveMatchesService
from services.future_matches import FutureMatchesService
from utils.theme_manager import get_theme_css, get_current_theme, set_theme, THEMES
import math
import requests
import html as html_lib
from datetime import datetime, timedelta


BASE_DIR = Path(__file__).parent


def load_css():
    """Charge le CSS du thème actuel dynamiquement"""
    # Appliquer le CSS du theme manager
    theme_css = get_theme_css()
    st.markdown(f"<style>{theme_css}</style>", unsafe_allow_html=True)

    # Charger aussi le style.css additionnel s'il existe
    css_path = BASE_DIR / "styles" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            additional_css = f.read()
            st.markdown(f"<style>{additional_css}</style>", unsafe_allow_html=True)


def apply_background_theme():
    """Applique le thème sélectionné - maintenant géré par le Theme Manager"""
    # Cette fonction est gardée pour compatibilité mais le CSS est injecté par load_css()
    pass


def render_theme_selector():
    """Affiche le selecteur de thème dans le header"""
    current_theme = get_current_theme()
    
    col1, col2, col3 = st.columns([1, 1, 1])
    
    theme_options = [
        ("dark_pro", "🌙", "Dark Pro"),
        ("light_pro", "☀️", "Light Pro"),
        ("blue_sky", "🌤️", "Blue Sky"),
    ]
    
    with col1:
        if st.button(
            f"🌙 Dark Pro",
            key="theme_dark",
            type="secondary" if current_theme != "dark_pro" else "primary",
            use_container_width=True
        ):
            set_theme("dark_pro")
            st.rerun()
    
    with col2:
        if st.button(
            f"☀️ Light Pro",
            key="theme_light",
            type="secondary" if current_theme != "light_pro" else "primary",
            use_container_width=True
        ):
            set_theme("light_pro")
            st.rerun()
    
    with col3:
        if st.button(
            f"🌤️ Blue Sky",
            key="theme_blue",
            type="secondary" if current_theme != "blue_sky" else "primary",
            use_container_width=True
        ):
            set_theme("blue_sky")
            st.rerun()


def get_query_param(name: str):
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def main():
    load_dotenv()
    load_css()

    st.set_page_config(page_title="Predict IA football LIVE", layout="wide", initial_sidebar_state="expanded")

    if "sidebar_open" not in st.session_state:
        st.session_state.sidebar_open = True
    if "active_page" not in st.session_state:
        st.session_state.active_page = "live"

    api = FootballAPI()

    sidebar.render_sidebar()
    apply_background_theme()
    active_page = st.session_state.get("active_page", "live")
    header.render_header(page=active_page)

    # Theme selector
    with st.container():
        st.markdown("<div style='margin: 8px 0;'>", unsafe_allow_html=True)
        render_theme_selector()
        st.markdown("</div>", unsafe_allow_html=True)

    with st.container():
        st.markdown("<div class='content-area'>", unsafe_allow_html=True)

        if not api.is_configured():
            st.markdown(
                """
            <div class='empty-state'>
                <h2>En attente de connexion API Football…</h2>
                <p>Configurez <strong>API_KEY</strong> et <strong>API_URL</strong> dans le fichier <strong>.env</strong>.</p>
            </div>
            """,
                unsafe_allow_html=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
            return

        analysis_fixture_id = get_query_param("analysis_fixture")
        if analysis_fixture_id:
            try:
                render_analysis_dashboard(
                    fixture_id=int(analysis_fixture_id),
                    home_team_id=int(get_query_param("home_team")),
                    away_team_id=int(get_query_param("away_team")),
                    league_id=int(get_query_param("league")),
                    season=int(get_query_param("season")),
                )
            except (TypeError, ValueError):
                st.error("Paramètres d'analyse invalides.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: MATCHS FUTURS
        # =========================
        if active_page == "future":
            st.markdown("<div class='future-filters-wrap'>", unsafe_allow_html=True)
            
            # Afficher info de recherche si active
            search_query = get_search_query()
            if search_query:
                col_search, col_clear = st.columns([3, 1])
                with col_search:
                    st.markdown(f"🔍 Recherche: **'{search_query}'**")
                with col_clear:
                    if st.button("❌ Effacer", key="clear_search_future", type="secondary"):
                        from components.header import clear_search
                        clear_search()
            
            filter_opt = st.radio(
                "Filtres",
                ["Aujourd'hui", "Demain", "Cette semaine"],
                horizontal=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)

            @st.cache_data(ttl=120)
            def fetch_future_matches_cached():
                api_inner = FootballAPI()
                raw, meta = api_inner.get_future_matches()
                parsed = FutureMatchesService.parse_matches(raw)
                return parsed, meta

            future_matches = []
            meta = {}
            error_msg = None

            with st.spinner("Récupération des matchs futurs..."):
                try:
                    future_matches, meta = fetch_future_matches_cached()
                except ConfigError as e:
                    error_msg = str(e)
                except RateLimitError:
                    error_msg = "Limite API atteinte, veuillez patienter."
                except APIError as e:
                    error_msg = f"Erreur API : {e}"
                except NetworkError as e:
                    error_msg = f"Erreur réseau : {e}"
                except requests.exceptions.Timeout:
                    error_msg = "Délai d'attente dépassé lors de la connexion à l'API."
                except Exception as e:
                    error_msg = f"Erreur inattendue : {e}"

            if error_msg:
                st.error(error_msg)
                st.markdown("</div>", unsafe_allow_html=True)
                return

            if not future_matches:
                st.info("Aucun match futur actuellement.")
                st.markdown("</div>", unsafe_allow_html=True)
                return

            now_local = datetime.now().astimezone()
            today = now_local.date()
            tomorrow = today + timedelta(days=1)
            end_of_week = today + timedelta(days=(6 - today.weekday()))  # dimanche

            def _keep(match: dict) -> bool:
                start_date_iso = match.get("start_date")  # YYYY-MM-DD
                try:
                    d = datetime.fromisoformat(start_date_iso).date()
                except Exception:
                    return False

                if filter_opt == "Aujourd'hui":
                    return d == today
                if filter_opt == "Demain":
                    return d == tomorrow
                return today <= d <= end_of_week

            filtered = [m for m in future_matches if _keep(m)]
            
            # Appliquer le filtre de recherche si présent
            search_query = get_search_query()
            if search_query:
                filtered = [m for m in filtered if matches_search_filter(m, search_query)]
                if not filtered:
                    st.info(f"Aucun match trouvé pour '{search_query}'.")
                    st.markdown("</div>", unsafe_allow_html=True)
                    return
            
            filtered.sort(key=lambda x: x.get("start_ts", 0))

            if not filtered:
                st.info("Aucun match pour ce filtre.")
                st.markdown("</div>", unsafe_allow_html=True)
                return

            for index, m in enumerate(filtered):
                home = m.get("home_team") or "—"
                away = m.get("away_team") or "—"
                home_logo = m.get("home_logo") or ""
                away_logo = m.get("away_logo") or ""
                league = m.get("league") or "—"
                league_country = m.get("league_country") or ""
                venue = m.get("venue") or ""
                fixture_id = m.get("fixture_id")
                home_team_id = m.get("home_team_id")
                away_team_id = m.get("away_team_id")
                league_id = m.get("league_id")
                season = m.get("season")
                start_time = m.get("start_time") or ""
                start_date_display = m.get("start_date_display") or m.get("start_date") or ""

                with st.container():
                    st.markdown("<div class='future-card-native'>", unsafe_allow_html=True)
                    top_cols = st.columns([2, 1, 2])
                    with top_cols[0]:
                        if home_logo:
                            st.image(home_logo, width=42)
                        st.markdown(f"**{home}**")
                    with top_cols[1]:
                        st.markdown("<div class='future-vs-native'>VS</div>", unsafe_allow_html=True)
                    with top_cols[2]:
                        if away_logo:
                            st.image(away_logo, width=42)
                        st.markdown(f"**{away}**")

                    st.markdown(
                        f"<div class='future-info-native'>{start_time} · {start_date_display}<br>{league} {league_country}<br>{venue}</div>",
                        unsafe_allow_html=True,
                    )

                    disabled = not all([fixture_id, home_team_id, away_team_id, league_id, season])
                    if st.button("📊 Analyser", key=f"future_analyze_{fixture_id}_{index}", disabled=disabled):
                        st.query_params["analysis_fixture"] = str(fixture_id)
                        st.query_params["home_team"] = str(home_team_id)
                        st.query_params["away_team"] = str(away_team_id)
                        st.query_params["league"] = str(league_id)
                        st.query_params["season"] = str(season)
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)
            return

        st.markdown(
            """
            <script>
            // reload the page every 15 seconds to get fresh data
            setTimeout(function(){ window.location.reload(); }, 15000);
            </script>
            """,
            unsafe_allow_html=True,
        )

        @st.cache_data(ttl=15)
        def fetch_live_matches_cached():
            api_inner = FootballAPI()
            raw, meta = api_inner.get_live_matches()
            parsed = LiveMatchesService.parse_matches(raw)
            return parsed, meta

        matches = []
        meta = {}
        error_msg = None

        with st.spinner("Récupération des matchs live..."):
            try:
                matches, meta = fetch_live_matches_cached()
            except ConfigError as e:
                error_msg = str(e)
            except RateLimitError:
                error_msg = "Limite API atteinte, veuillez patienter."
            except APIError as e:
                error_msg = f"Erreur API : {e}"
            except NetworkError as e:
                error_msg = f"Erreur réseau : {e}"
            except requests.exceptions.Timeout:
                error_msg = "Délai d'attente dépassé lors de la connexion à l'API."
            except Exception as e:
                error_msg = f"Erreur inattendue : {e}"

        if error_msg:
            st.error(error_msg)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        if not matches:
            st.info("Aucun match live actuellement.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # Appliquer le filtre de recherche si présent
        search_query = get_search_query()
        if search_query:
            matches = [m for m in matches if matches_search_filter(m, search_query)]
            if not matches:
                st.info(f"Aucun match live trouvé pour '{search_query}'.")
                st.markdown("</div>", unsafe_allow_html=True)
                return

        total_matches = len(matches)
        original_total = meta.get("total", total_matches) if meta else total_matches
        fetched_at = meta.get("fetched_at") if meta else None

        # Afficher le header live avec bouton effacer recherche si nécessaire
        header_cols = st.columns([1, 2, 1]) if not search_query else st.columns([1, 2, 1, 1])
        
        with header_cols[0]:
            html = """
            <div style='display:flex;align-items:center;gap:8px'>
              <div style='width:14px;height:14px;border-radius:50%;background:#e02424;animation: pulse 1s infinite'></div>
              <div style='font-weight:600'>LIVE</div>
              <div style='margin-left:8px;color:#666'>&nbsp;•&nbsp;</div>
              <div style='font-weight:600;margin-left:4px'>__TOTAL__</div>
            </div>
            <style>@keyframes pulse {0% {transform: scale(1);}50% {transform: scale(1.4);opacity:0.7;}100% {transform: scale(1);opacity:1;}}</style>
            """
            html = html.replace("__TOTAL__", str(total_matches))
            st.markdown(html, unsafe_allow_html=True)
        with header_cols[1]:
            # Afficher info de filtrage si recherche active
            if search_query:
                st.markdown(f"<div style='color:#666'>🔍 Recherche: **'{search_query}'** • {total_matches} résultat(s)</div>", unsafe_allow_html=True)
            elif fetched_at:
                st.markdown(f"<div style='color:#666'>Dernière mise à jour : {fetched_at}</div>", unsafe_allow_html=True)
        
        # Bouton effacer si recherche active
        if search_query:
            with header_cols[2]:
                if st.button("❌ Effacer", key="clear_search_live", type="secondary"):
                    from components.header import clear_search
                    clear_search()
            with header_cols[3]:
                st.caption(f"{total_matches}/{original_total} matchs")
                st.markdown("<div style='color:green;font-weight:600'>API connecté</div>", unsafe_allow_html=True)
        else:
            with header_cols[2]:
                st.markdown("<div style='color:green;font-weight:600'>API connecté</div>", unsafe_allow_html=True)

        # Group matches by competition and render list
        grouped = {}
        for m in matches:
            key = m.get("league") or "Autres"
            country = m.get("league_country") or ""
            flag = m.get("league_flag") or ""
            if key not in grouped:
                grouped[key] = {"items": [], "country": country, "flag": flag}
            grouped[key]["items"].append(m)

        parts = ["<div class='matches-list-container'>"]
        for league, info in grouped.items():
            items = info.get("items", [])
            country = info.get("country") or ""
            flag = info.get("flag") or ""
            # competition header: include country flag image and country name if available
            # NOTE: `comp-header` is hidden by CSS, but we still generate valid HTML to avoid layout glitches.
            country_html = (
                f"<img src='{flag}' class='comp-country-flag' alt='{country}' onerror=\"this.style.display='none'\"/>"
                f" <span class='comp-country'>{country}</span>"
                if flag or country
                else ""
            )
            parts.append(
                "<div class='comp-block'>"
                "<div class='comp-matches'>"
            )

            for it in items:
                home = it.get("home_team") or "—"
                away = it.get("away_team") or "—"
                home_logo = it.get("home_logo") or ""
                away_logo = it.get("away_logo") or ""
                minute = it.get("minute")
                status = it.get("status") or ""
                venue = it.get("venue") or ""
                fixture_id = it.get("fixture_id")
                home_team_id = it.get("home_team_id")
                away_team_id = it.get("away_team_id")
                league_id = it.get("league_id")
                season = it.get("season")
                analysis_link = "#"
                if fixture_id and home_team_id and away_team_id and league_id and season:
                    analysis_link = (
                        f"?analysis_fixture={fixture_id}&home_team={home_team_id}"
                        f"&away_team={away_team_id}&league={league_id}&season={season}"
                    )
                minute_text = f"{minute}'" if minute is not None and str(minute).strip() != "" else ""
                score_display = (
                    f"{it.get('home_score') if it.get('home_score') is not None else '-'}"
                    f" - {it.get('away_score') if it.get('away_score') is not None else '-'}"
                )

                league_flag = it.get('league_flag') or ''
                league_country = it.get('league_country') or ''
                country_html = (
                    f"<img src='{league_flag}' class='comp-country-flag' alt='{league_country}' onerror=\"this.style.display='none'\"/> <span class='comp-country-small'>{league_country}</span>"
                    if league_flag or league_country
                    else ""
                )

                # Special stacked presentation for OshMU Aldier
                special_team = "OshMU Aldier"
                if home == special_team or away == special_team:
                    # determine which side is the opponent
                    if home == special_team:
                        osh_name = home
                        osh_logo = home_logo
                        opp_name = away
                        opp_logo = away_logo
                    else:
                        osh_name = away
                        osh_logo = away_logo
                        opp_name = home
                        opp_logo = home_logo

                    row_html = (
                        "<div class='match-row'>"
                        "<div class='match-band special'>"
                        f"  <div class='special-left'><div class='team-name-big'>{osh_name}</div></div>"
                        f"  <div class='special-center'><div class='score'>{score_display}</div><div class='minute-text-small'>{minute_text} {status}</div></div>"
                        f"  <div class='special-right'><div class='team-name-big'>{opp_name}</div></div>"
                        f"  <div class='band-meta'><div class='competition-name'>{league} {country_html}</div><div class='meta-line'>{venue}</div><a class='analysis-button compact' href='{analysis_link}'>📊 Analyser</a></div>"
                        "</div>"
                        "</div>"
                    )
                else:
                    row_html = (
                        "<div class='match-row'>"
                        "<div class='match-band'>"
                        f"  <div class='team team-left'><img src='{home_logo}' class='logo' alt='{home}' onerror=\"this.style.display='none'\"/><div class='team-name'>{home}</div></div>"
                        f"  <div class='band-center'><div class='score'>{score_display}</div><div class='minute-text-small'>{minute_text} {status}</div></div>"
                        f"  <div class='team team-right'><img src='{away_logo}' class='logo' alt='{away}' onerror=\"this.style.display='none'\"/><div class='team-name'>{away}</div></div>"
                        f"  <div class='band-meta'><div class='competition-name'>{league} {country_html}</div><div class='meta-line'>{venue}</div><a class='analysis-button compact' href='{analysis_link}'>📊 Analyser</a></div>"
                        "</div>"
                        "</div>"
                    )
                parts.append(row_html)

            parts.append("</div></div>")

        parts.append("</div>")
        full_html = "\n".join(parts)

        st.markdown(full_html, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
