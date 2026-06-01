import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from components import sidebar, header
from components.header import get_search_query, matches_search_filter, matches_search_score, render_datetime_header
from components.analysis_dashboard import render_analysis_dashboard
from components.betting_page import render_betting_page, render_floating_bet_button
from modules.top_over25_live.top_over25_ui import render_top_over25_page
from modules.daily_predictions.daily_predictions_ui import render_daily_predictions_page
from modules.history_results.history_results_ui import render_history_page
from modules.top_under25_live.under25_ui import render_top_under25_page
from modules.top_victories.victory_ui import render_top_victories_page
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

    # Afficher date/heure en haut - design premium responsive
    render_datetime_header()

    sidebar.render_sidebar()
    apply_background_theme()

    active_page = st.session_state.get("active_page", "live")
    header.render_header(page=active_page)

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
        # Si un fixture est dans l'URL et que la page n'est PAS live/future
        # (ou qu'elle n'a pas encore été basculée), afficher l'analyse
        if analysis_fixture_id:
            # Auto-basculer vers "analysis" si on vient d'un lien direct (active_page = live ou future)
            if active_page in ("live", "future"):
                st.session_state["active_page"] = "analysis"
                active_page = "analysis"
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
        # Page: PARIS
        # =========================
        if active_page == "paris":
            # Récupérer les matchs live et futurs pour la sélection de paris
            @st.cache_data(ttl=30)
            def _fetch_live_for_betting():
                _api = FootballAPI()
                raw, _ = _api.get_live_matches()
                return LiveMatchesService.parse_matches(raw)

            @st.cache_data(ttl=120)
            def _fetch_future_for_betting():
                from datetime import date, timedelta as _td
                _api = FootballAPI()
                _now_ts = datetime.now().timestamp()
                collected = []
                seen_ids = set()

                # Aujourd'hui + demain par date
                for _d in [date.today(), date.today() + _td(days=1)]:
                    try:
                        raw, _ = _api.get_fixtures_by_date(_d.isoformat())
                        parsed = FutureMatchesService.parse_matches(raw)
                        for m in parsed:
                            fid = m.get("fixture_id")
                            if fid and fid not in seen_ids and m.get("start_ts", 0) > _now_ts:
                                seen_ids.add(fid)
                                collected.append(m)
                    except Exception:
                        pass

                # Prochains 50 matchs (couvre toute la semaine)
                try:
                    raw2, _ = _api.get_fixtures_next_n(n=50)
                    parsed2 = FutureMatchesService.parse_matches(raw2)
                    for m in parsed2:
                        fid = m.get("fixture_id")
                        if fid and fid not in seen_ids and m.get("start_ts", 0) > _now_ts:
                            seen_ids.add(fid)
                            collected.append(m)
                except Exception:
                    pass

                # Fallback : get_future_matches standard
                if not collected:
                    try:
                        raw3, _ = _api.get_future_matches()
                        parsed3 = FutureMatchesService.parse_matches(raw3)
                        for m in parsed3:
                            fid = m.get("fixture_id")
                            if fid and fid not in seen_ids and m.get("start_ts", 0) > _now_ts:
                                seen_ids.add(fid)
                                collected.append(m)
                    except Exception:
                        pass

                # Trier par date de début
                collected.sort(key=lambda x: x.get("start_ts", 0))
                return collected

            _live_bets, _future_bets = [], []
            try:
                _live_bets = _fetch_live_for_betting()
            except Exception:
                pass
            try:
                _future_bets = _fetch_future_for_betting()
            except Exception:
                pass

            render_betting_page(api=api, live_matches=_live_bets, future_matches=_future_bets)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: TOP VICTOIRES IA
        # =========================
        if active_page == "victories":
            render_top_victories_page(api=api)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: TOP +2.5 BUTS
        # =========================
        if active_page == "over25":
            render_top_over25_page(api=api)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: PREDICTIONS DU JOUR
        # =========================
        if active_page == "daily":
            render_daily_predictions_page(api=api)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: TOP UNDER 2.5
        # =========================
        if active_page == "under25":
            render_top_under25_page(api=api)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: HISTORIQUE
        # =========================
        if active_page == "history":
            render_history_page(api=api)
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # =========================
        # Page: MATCHS FUTURS
        # =========================
        if active_page == "future":
            now_local = datetime.now().astimezone()
            now_ts = now_local.timestamp()
            today = now_local.date()
            tomorrow = today + timedelta(days=1)

            # --- Filtres haut de page ---
            st.markdown("<div class='future-filters-wrap'>", unsafe_allow_html=True)
            
            filt_cols = st.columns([2, 2, 2])
            with filt_cols[0]:
                date_mode = st.selectbox(
                    "📅 Période",
                    ["Aujourd'hui", "Demain", "Cette semaine", "Semaine prochaine", "Date personnalisée"],
                    key="future_date_mode",
                    label_visibility="collapsed",
                )
            with filt_cols[1]:
                if date_mode == "Date personnalisée":
                    selected_date = st.date_input(
                        "Date",
                        value=today,
                        min_value=today,
                        max_value=today + timedelta(days=60),
                        key="future_custom_date",
                        label_visibility="collapsed",
                    )
                else:
                    selected_date = None
                    st.empty()
            with filt_cols[2]:
                search_query = get_search_query()
                if search_query:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.caption(f"🔍 Filtre: **{search_query}**")
                    with c2:
                        if st.button("❌", key="clr_future"):
                            from components.header import clear_search
                            clear_search()

            st.markdown("</div>", unsafe_allow_html=True)

            # --- Calcul de la plage de dates ---
            if date_mode == "Aujourd'hui":
                date_range = [today]
            elif date_mode == "Demain":
                date_range = [tomorrow]
            elif date_mode == "Cette semaine":
                date_range = [today + timedelta(days=i) for i in range(7)]
            elif date_mode == "Semaine prochaine":
                date_range = [today + timedelta(days=7 + i) for i in range(7)]
            else:
                date_range = [selected_date] if selected_date else [today]

            # --- FETCH (TTL=60s pour aujourd'hui, 300s sinon) ---
            _today_ttl = 60 if date_mode == "Aujourd'hui" else 300

            @st.cache_data(ttl=_today_ttl)
            def fetch_fixtures_by_date_cached(date_str: str):
                api_inner = FootballAPI()
                raw, meta = api_inner.get_fixtures_by_date(date_str)
                return FutureMatchesService.parse_matches(raw), meta

            @st.cache_data(ttl=300)
            def fetch_future_matches_cached():
                api_inner = FootballAPI()
                raw, meta = api_inner.get_future_matches()
                return FutureMatchesService.parse_matches(raw), meta

            future_matches: List[Dict[str, Any]] = []
            meta: Dict[str, Any] = {}
            error_msg = None

            with st.spinner("Chargement..."):
                try:
                    if date_mode in ["Aujourd'hui", "Demain", "Date personnalisée"]:
                        future_matches, meta = fetch_fixtures_by_date_cached(date_range[0].isoformat())
                    else:
                        future_matches, meta = fetch_future_matches_cached()
                except ConfigError as e:
                    error_msg = str(e)
                except RateLimitError:
                    error_msg = "Limite API atteinte, veuillez patienter."
                except (APIError, NetworkError) as e:
                    error_msg = str(e)
                except Exception as e:
                    error_msg = str(e)

            if error_msg:
                st.error(error_msg)
                st.markdown("</div>", unsafe_allow_html=True)
                return

            # --- Filtre par plage de dates ET exclure tout match déjà commencé ---
            def _in_date_range(match: dict) -> bool:
                start_ts = match.get("start_ts", 0)
                start_date_iso = match.get("start_date")
                try:
                    d = datetime.fromisoformat(start_date_iso).date()
                    in_range = d in date_range
                    # Exclure tout match dont l'heure de début est passée (>= maintenant)
                    not_started = start_ts >= now_ts
                    return in_range and not_started
                except Exception:
                    return False

            filtered = [m for m in future_matches if _in_date_range(m)]
            if not filtered and date_mode not in ["Aujourd'hui", "Demain", "Date personnalisée"]:
                filtered = [m for m in future_matches if m.get("start_ts", 0) >= now_ts]

            # --- Filtre recherche ---
            search_query = get_search_query()
            if search_query:
                filtered = [m for m in filtered if matches_search_filter(m, search_query)]
                filtered.sort(key=lambda x: -matches_search_score(x, search_query))
            else:
                filtered.sort(key=lambda x: x.get("start_ts", 0))
            st.session_state["future_match_count"] = len(filtered)

            if not filtered:
                st.info("Aucun match pour ce filtre.")
                st.markdown("</div>", unsafe_allow_html=True)
                return

            # --- Filtre compétitions / pays (sans re-fetch API) ---
            all_leagues = sorted(set(m.get("league", "Autres") for m in filtered if m.get("league")))
            all_countries = sorted(set(m.get("league_country", "") for m in filtered if m.get("league_country")))

            filter_row = st.columns([2, 2])
            with filter_row[0]:
                selected_league = st.selectbox(
                    "Compétition",
                    ["Toutes"] + all_leagues,
                    key="future_league_filter",
                    label_visibility="collapsed",
                    placeholder="🏆 Toutes les compétitions",
                )
            with filter_row[1]:
                selected_country = st.selectbox(
                    "Pays",
                    ["Tous"] + all_countries,
                    key="future_country_filter",
                    label_visibility="collapsed",
                    placeholder="🌍 Tous les pays",
                )

            if selected_league != "Toutes":
                filtered = [m for m in filtered if m.get("league") == selected_league]
            if selected_country != "Tous":
                filtered = [m for m in filtered if m.get("league_country") == selected_country]

            st.caption(f"📋 {len(filtered)} match(s) trouvé(s)")

            if not filtered:
                st.info("Aucun match pour ces filtres.")
                st.markdown("</div>", unsafe_allow_html=True)
                return

            # ── Bouton ticket flottant (avant la liste) ──────────────
            render_floating_bet_button(api)

            # --- Grouper par compétition ---
            grouped_future: Dict[str, list] = {}
            for m in filtered:
                key = m.get("league") or "Autres"
                if key not in grouped_future:
                    grouped_future[key] = []
                grouped_future[key].append(m)

            for league_name, league_matches in grouped_future.items():
                sample = league_matches[0]
                league_flag = sample.get("league_flag") or ""
                league_country = sample.get("league_country") or ""

                flag_html = f"<img src='{league_flag}' width='18' style='vertical-align:middle;margin-right:6px;border-radius:2px;' onerror=\"this.style.display='none'\"/>" if league_flag else ""
                st.markdown(
                    f"<div style='display:flex;align-items:center;gap:6px;padding:8px 0 4px;border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:8px;'>"
                    f"{flag_html}<span style='font-weight:700;font-size:0.95rem;'>{league_name}</span>"
                    f"<span style='color:#888;font-size:0.8rem;margin-left:4px;'>{league_country}</span>"
                    f"<span style='margin-left:auto;color:#888;font-size:0.8rem;'>{len(league_matches)} match(s)</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

                for index, m in enumerate(league_matches):
                    home = m.get("home_team") or "—"
                    away = m.get("away_team") or "—"
                    home_logo = m.get("home_logo") or ""
                    away_logo = m.get("away_logo") or ""
                    league = m.get("league") or "—"
                    venue = m.get("venue") or ""
                    fixture_id = m.get("fixture_id")
                    home_team_id = m.get("home_team_id")
                    away_team_id = m.get("away_team_id")
                    league_id_val = m.get("league_id")
                    season = m.get("season")
                    start_time = m.get("start_time") or ""
                    start_date_display = m.get("start_date_display") or m.get("start_date") or ""

                    with st.container():
                        st.markdown(
                            f"""
                            <div style='
                                background:linear-gradient(135deg,rgba(255,255,255,0.04),rgba(255,255,255,0.02));
                                border:1px solid rgba(255,255,255,0.08);
                                border-radius:12px;
                                padding:12px 16px;
                                margin-bottom:8px;
                            '>""",
                            unsafe_allow_html=True,
                        )
                        top_cols = st.columns([3, 1, 3, 2])
                        with top_cols[0]:
                            if home_logo:
                                st.image(home_logo, width=32)
                            st.markdown(f"**{home}**")
                        with top_cols[1]:
                            st.markdown(
                                f"<div style='text-align:center;padding:6px 0;'>"
                                f"<div style='font-size:0.7rem;color:#888;'>{start_time}</div>"
                                f"<div style='font-weight:700;color:#00d4ff;'>VS</div>"
                                f"<div style='font-size:0.65rem;color:#666;'>{start_date_display}</div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )
                        with top_cols[2]:
                            if away_logo:
                                st.image(away_logo, width=32)
                            st.markdown(f"**{away}**")
                        with top_cols[3]:
                            if venue:
                                st.caption(f"📍 {venue}")
                            disabled = not all([fixture_id, home_team_id, away_team_id, league_id_val, season])
                            if st.button("📊", key=f"future_analyze_{fixture_id}_{index}", disabled=disabled, help="Analyser", use_container_width=True):
                                st.session_state["active_page"] = "analysis"
                                st.query_params["analysis_fixture"] = str(fixture_id)
                                st.query_params["home_team"] = str(home_team_id)
                                st.query_params["away_team"] = str(away_team_id)
                                st.query_params["league"] = str(league_id_val)
                                st.query_params["season"] = str(season)
                                st.rerun()
                        st.markdown("</div>", unsafe_allow_html=True)
                    # ── Bouton Paris ─────────────────────────────────────────
                    with st.container():
                        bet_cols = st.columns([6, 1])
                        with bet_cols[1]:
                            opened_f = st.session_state.get(f"bet_open_{fixture_id}", False)
                            label_f  = "🔒 Fermer" if opened_f else "🎰 Parier"
                            if st.button(label_f, key=f"fut_bet_{fixture_id}_{index}", use_container_width=True):
                                st.session_state[f"bet_open_{fixture_id}"] = not opened_f
                                st.rerun()

                    # ── Panneau paris déroulant ──────────────────────────────
                    if st.session_state.get(f"bet_open_{fixture_id}", False):
                        from components.betting_page import render_inline_bet_panel
                        render_inline_bet_panel(m, match_type="future")

            st.markdown("</div>", unsafe_allow_html=True)
            return

        st.markdown(
            """
            <script>
            // DÉSACTIVÉ : Rechargement automatique cause des ventes involontaires
            // setTimeout(function(){ window.location.reload(); }, 15000);
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
                st.session_state["live_match_count"] = len(matches)
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

        # --- Filtre recherche ---
        search_query = get_search_query()
        if search_query:
            matches = [m for m in matches if matches_search_filter(m, search_query)]
            matches = sorted(matches, key=lambda x: -matches_search_score(x, search_query))

        fetched_at = meta.get("fetched_at") if meta else None

        # --- Filtres compétition / pays Live (purement local, pas d'appel API) ---
        all_live_leagues = sorted(set(m.get("league", "") for m in matches if m.get("league")))
        all_live_countries = sorted(set(m.get("league_country", "") for m in matches if m.get("league_country")))

        live_cols = st.columns([1, 2, 2, 1])
        with live_cols[0]:
            st.markdown(
                "<div style='display:flex;align-items:center;gap:6px;padding-top:8px;'>"
                "<div style='width:10px;height:10px;border-radius:50%;background:#e02424;"
                "animation:_lp 1s infinite'></div><b>LIVE</b></div>"
                "<style>@keyframes _lp{0%{transform:scale(1)}50%{transform:scale(1.5);opacity:.6}100%{transform:scale(1)}}</style>",
                unsafe_allow_html=True,
            )
        with live_cols[1]:
            sel_live_league = st.selectbox(
                "Compétition",
                ["Toutes"] + all_live_leagues,
                key="live_league_filter",
                label_visibility="collapsed",
            )
        with live_cols[2]:
            sel_live_country = st.selectbox(
                "Pays",
                ["Tous"] + all_live_countries,
                key="live_country_filter",
                label_visibility="collapsed",
            )
        with live_cols[3]:
            if search_query:
                if st.button("❌", key="clear_search_live"):
                    from components.header import clear_search
                    clear_search()

        # Appliquer filtres locaux (pas de re-fetch)
        if sel_live_league != "Toutes":
            matches = [m for m in matches if m.get("league") == sel_live_league]
        if sel_live_country != "Tous":
            matches = [m for m in matches if m.get("league_country") == sel_live_country]

        if not matches:
            st.info("Aucun match live pour ces filtres.")
            st.markdown("</div>", unsafe_allow_html=True)
            return

        # ── Bouton ticket flottant (avant la liste) ──────────────────
        render_floating_bet_button(api)

        total_matches = len(matches)
        info_parts = [f"**{total_matches}** match(s) en direct"]
        if search_query:
            info_parts.append(f"🔍 '{search_query}'")
        if fetched_at:
            info_parts.append(f"màj {fetched_at[:19]}")
        st.caption(" · ".join(info_parts))

        # Group matches by competition and render list
        grouped = {}
        for m in matches:
            key = m.get("league") or "Autres"
            country = m.get("league_country") or ""
            flag = m.get("league_flag") or ""
            if key not in grouped:
                grouped[key] = {"items": [], "country": country, "flag": flag}
            grouped[key]["items"].append(m)

        from components.betting_page import render_inline_bet_panel

        for league_name, info in grouped.items():
            items   = info.get("items", [])
            country = info.get("country") or ""
            flag    = info.get("flag") or ""
            flag_html = (
                f"<img src='{flag}' width='16' style='vertical-align:middle;margin-right:5px;"
                f"border-radius:2px;' onerror=\"this.style.display='none'\"/>"
                if flag else ""
            )
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:6px;padding:8px 0 4px;"
                f"border-bottom:1px solid rgba(255,255,255,0.1);margin-bottom:6px;'>"
                f"{flag_html}<span style='font-weight:700;font-size:0.92rem;'>{league_name}</span>"
                f"<span style='color:#888;font-size:0.78rem;margin-left:4px;'>{country}</span>"
                f"<span style='margin-left:auto;color:#888;font-size:0.78rem;'>{len(items)} match(s)</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

            for idx, it in enumerate(items):
                home        = it.get("home_team") or "—"
                away        = it.get("away_team") or "—"
                home_logo   = it.get("home_logo") or ""
                away_logo   = it.get("away_logo") or ""
                minute      = it.get("minute")
                status      = it.get("status") or ""
                home_score  = it.get("home_score")
                away_score  = it.get("away_score")
                fixture_id  = it.get("fixture_id")
                home_team_id = it.get("home_team_id")
                away_team_id = it.get("away_team_id")
                league_id   = it.get("league_id")
                season      = it.get("season")

                minute_text   = f"{minute}'" if minute is not None and str(minute).strip() else "LIVE"
                hs = home_score if home_score is not None else "-"
                as_ = away_score if away_score is not None else "-"

                with st.container():
                    st.markdown(
                        f"<div style='background:linear-gradient(135deg,rgba(255,255,255,0.05),"
                        f"rgba(255,255,255,0.02));border:1px solid rgba(220,38,38,0.25);"
                        f"border-left:3px solid #dc2626;border-radius:10px;"
                        f"padding:10px 14px;margin-bottom:4px;'>",
                        unsafe_allow_html=True,
                    )
                    row_cols = st.columns([3, 2, 3, 1, 1])
                    with row_cols[0]:
                        logo_h = f"<img src='{home_logo}' width='22' style='vertical-align:middle;margin-right:6px;border-radius:3px;' onerror=\"this.style.display='none'\"/>" if home_logo else ""
                        st.markdown(f"{logo_h}**{home}**", unsafe_allow_html=True)
                    with row_cols[1]:
                        st.markdown(
                            f"<div style='text-align:center;'>"
                            f"<span style='background:#dc2626;color:#fff;border-radius:4px;"
                            f"padding:2px 7px;font-size:0.68rem;font-weight:900;'>● {minute_text}</span><br>"
                            f"<span style='font-size:1.1rem;font-weight:900;color:#fff;'>{hs} – {as_}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with row_cols[2]:
                        logo_a = f"<img src='{away_logo}' width='22' style='vertical-align:middle;margin-right:6px;border-radius:3px;' onerror=\"this.style.display='none'\"/>" if away_logo else ""
                        st.markdown(f"{logo_a}**{away}**", unsafe_allow_html=True)
                    with row_cols[3]:
                        disabled_analyze = not all([fixture_id, home_team_id, away_team_id, league_id, season])
                        if st.button("📊", key=f"lv_analyze_{fixture_id}_{idx}", disabled=disabled_analyze, help="Analyser"):
                            st.session_state["active_page"] = "analysis"
                            st.query_params["analysis_fixture"] = str(fixture_id)
                            st.query_params["home_team"] = str(home_team_id)
                            st.query_params["away_team"] = str(away_team_id)
                            st.query_params["league"] = str(league_id)
                            st.query_params["season"] = str(season)
                            st.rerun()
                    with row_cols[4]:
                        bet_key = f"lv_bet_{fixture_id}_{idx}"
                        opened = st.session_state.get(f"bet_open_{fixture_id}", False)
                        label  = "🔒" if opened else "🎰"
                        if st.button(label, key=bet_key, help="Parier sur ce match"):
                            st.session_state[f"bet_open_{fixture_id}"] = not opened
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                # ── Panneau paris déroulant ──────────────────────────────────
                if st.session_state.get(f"bet_open_{fixture_id}", False):
                    render_inline_bet_panel(it, match_type="live")

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
