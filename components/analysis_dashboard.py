import html as html_lib
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st

from ai_engine.bet_suggestion_engine import analyze_bet_opportunities
from ai_engine.elo_rating import calculate_elo
from ai_engine.form_analyzer import analyze_form
from ai_engine.live_context_engine import build_live_context
from ai_engine.probability_engine import calculate_probabilities
from ai_engine.smart_stats_fallback import estimate_missing_stats, mark_estimated
from ai_engine.predictions_engine import generate_full_predictions, render_predictions_section
from services.football_api import FootballAPI


def _response(data: Dict[str, Any]) -> Any:
    if isinstance(data, dict):
        return data.get("response") or []
    return data or []


def _first_response(data: Dict[str, Any]) -> Dict[str, Any]:
    items = _response(data)
    if isinstance(items, list) and items:
        return items[0] or {}
    if isinstance(items, dict):
        return items
    return {}


def _stat_map(stat_item: Dict[str, Any]) -> Dict[str, Any]:
    stats = {}
    for row in stat_item.get("statistics") or []:
        stat_type = row.get("type")
        if stat_type:
            stats[stat_type] = row.get("value")
    return stats


def _num(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace("%", "").strip()
    try:
        return int(float(text))
    except ValueError:
        return 0


def _display_value(value: Any) -> Any:
    if value is None or value == "—":
        return "Non disponible"
    return value


def _stat_value(stats: Dict[str, Any], aliases: List[str], fallback: Any = 0) -> Any:
    normalized = {str(key).lower().strip(): value for key, value in stats.items()}
    for alias in aliases:
        key = alias.lower().strip()
        if key in normalized and normalized[key] is not None:
            return normalized[key]
    return fallback


def _team_stat_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    response = _response(data)
    if isinstance(response, dict):
        return response
    if isinstance(response, list) and response:
        return response[0] or {}
    return {}


def _team_average_goals(team_stats_data: Dict[str, Any], side: str) -> float:
    payload = _team_stat_payload(team_stats_data)
    goals = payload.get("goals") or {}
    section = goals.get("for" if side == "for" else "against") or {}
    average = section.get("average") or {}
    total = average.get("total")
    try:
        return float(total or 0)
    except (TypeError, ValueError):
        return 0.0


def _fixture_score(item: Dict[str, Any]) -> str:
    goals = item.get("goals") or {}
    home = goals.get("home")
    away = goals.get("away")
    return f"{home if home is not None else '-'} - {away if away is not None else '-'}"


def _team_form(fixtures: List[Dict[str, Any]], team_id: int) -> Dict[str, Any]:
    wins = draws = losses = goals_for = goals_against = 0
    rows = []
    for item in fixtures[:5]:
        teams = item.get("teams") or {}
        goals = item.get("goals") or {}
        home = teams.get("home") or {}
        away = teams.get("away") or {}
        is_home = home.get("id") == team_id
        gf = goals.get("home") if is_home else goals.get("away")
        ga = goals.get("away") if is_home else goals.get("home")
        gf = gf if gf is not None else 0
        ga = ga if ga is not None else 0
        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1
            result = "V"
        elif gf < ga:
            losses += 1
            result = "D"
        else:
            draws += 1
            result = "N"
        rows.append({"opponent": (away if is_home else home).get("name") or "—", "score": _fixture_score(item), "result": result})
    return {"wins": wins, "draws": draws, "losses": losses, "goals_for": goals_for, "goals_against": goals_against, "rows": rows}


def _standing_for_team(standings_data: Dict[str, Any], team_id: int) -> Dict[str, Any]:
    for league in _response(standings_data):
        for group in (league.get("league") or {}).get("standings") or []:
            for row in group:
                team = row.get("team") or {}
                if team.get("id") == team_id:
                    return row
    return {}


@st.cache_data(ttl=180)
def fetch_analysis_data(fixture_id: int, home_team_id: int, away_team_id: int, league_id: int, season: int) -> Dict[str, Any]:
    api = FootballAPI(timeout=12, max_retries=3)
    return {
        "fixture": api.get_fixture_detail(fixture_id),
        "statistics": api.get_fixture_statistics(fixture_id),
        "events": api.get_fixture_events(fixture_id),
        "lineups": api.get_fixture_lineups(fixture_id),
        "home_recent": api.get_team_recent_fixtures(home_team_id, 5),
        "away_recent": api.get_team_recent_fixtures(away_team_id, 5),
        "home_team_stats": api.get_team_statistics(league_id, season, home_team_id),
        "away_team_stats": api.get_team_statistics(league_id, season, away_team_id),
        "h2h": api.get_head_to_head(home_team_id, away_team_id, 5),
        "standings": api.get_standings(league_id, season),
    }


def render_analysis_dashboard(fixture_id: int, home_team_id: int, away_team_id: int, league_id: int, season: int):
    nav_c1, nav_c2, nav_c3 = st.columns([2, 1, 1])
    with nav_c1:
        if st.button("\u2190 Retour aux matchés", use_container_width=True):
            st.query_params.clear()
            st.session_state["active_page"] = st.session_state.get("active_page", "live")
            st.rerun()
    with nav_c2:
        if st.button("\U0001f534 Matchs Live", use_container_width=True):
            st.query_params.clear()
            st.session_state["active_page"] = "live"
            st.rerun()
    with nav_c3:
        if st.button("\U0001f4c5 Matchs Futurs", use_container_width=True):
            st.query_params.clear()
            st.session_state["active_page"] = "future"
            st.rerun()

    with st.spinner("Chargement de l'analyse réelle API-Football..."):
        data = fetch_analysis_data(fixture_id, home_team_id, away_team_id, league_id, season)

    fixture = _first_response(data["fixture"])
    fixture_info = fixture.get("fixture") or {}
    teams = fixture.get("teams") or {}
    goals = fixture.get("goals") or {}
    league = fixture.get("league") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    venue = fixture_info.get("venue") or {}
    status = fixture_info.get("status") or {}

    home_name = home.get("name") or "Equipe domicile"
    away_name = away.get("name") or "Equipe extérieur"
    score = f"{goals.get('home') if goals.get('home') is not None else '-'} - {goals.get('away') if goals.get('away') is not None else '-'}"
    time_label = f"{status.get('elapsed')}’ {status.get('short') or ''}" if status.get("elapsed") else fixture_info.get("date", "")

    st.markdown("<div class='analysis-shell'>", unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='analysis-hero'>
          <div class='analysis-team'><img src='{html_lib.escape(str(home.get('logo') or ''))}'/><h2>{html_lib.escape(home_name)}</h2></div>
          <div class='analysis-score'><div>{html_lib.escape(score)}</div><span>{html_lib.escape(str(time_label))}</span></div>
          <div class='analysis-team'><img src='{html_lib.escape(str(away.get('logo') or ''))}'/><h2>{html_lib.escape(away_name)}</h2></div>
        </div>
        <div class='analysis-meta'>{html_lib.escape(str(league.get('name') or '—'))} · {html_lib.escape(str(venue.get('name') or 'Stade non disponible'))}</div>
        """,
        unsafe_allow_html=True,
    )

    stats_items = _response(data["statistics"])
    home_stats = _stat_map(stats_items[0]) if isinstance(stats_items, list) and len(stats_items) > 0 else {}
    away_stats = _stat_map(stats_items[1]) if isinstance(stats_items, list) and len(stats_items) > 1 else {}
    stat_names = [
        ("Possession", ["Ball Possession", "Possession"], "Non disponible"),
        ("Tirs", ["Total Shots", "Shots Total", "Total shots"], 0),
        ("Tirs cadrés", ["Shots on Goal", "Shots on goal", "On Target"], 0),
        ("Corners", ["Corner Kicks", "Corners"], 0),
        ("Fautes", ["Fouls"], 0),
        ("Cartons jaunes", ["Yellow Cards"], 0),
        ("Cartons rouges", ["Red Cards"], 0),
        ("Expected goals", ["expected_goals", "Expected Goals", "xG"], "Non disponible"),
    ]

    st.markdown("### 📊 Statistiques match")
    for name, aliases, fallback in stat_names:
        left = _stat_value(home_stats, aliases, fallback)
        right = _stat_value(away_stats, aliases, fallback)
        left_num = _num(left)
        right_num = _num(right)
        total = max(left_num + right_num, 1)
        st.markdown(f"**{name}**")
        cols = st.columns([1, 3, 1])
        cols[0].metric(home_name, _display_value(left))
        cols[1].progress(min(left_num / total, 1.0))
        cols[2].metric(away_name, _display_value(right))

    home_recent = _response(data["home_recent"])
    away_recent = _response(data["away_recent"])
    home_form = analyze_form(home_recent, home_team_id)
    away_form = analyze_form(away_recent, away_team_id)
    home_team_avg_for = _team_average_goals(data["home_team_stats"], "for")
    home_team_avg_against = _team_average_goals(data["home_team_stats"], "against")
    away_team_avg_for = _team_average_goals(data["away_team_stats"], "for")
    away_team_avg_against = _team_average_goals(data["away_team_stats"], "against")
    if home_team_avg_for:
        home_form["avg_goals_for"] = home_team_avg_for
    if home_team_avg_against:
        home_form["avg_goals_against"] = home_team_avg_against
    if away_team_avg_for:
        away_form["avg_goals_for"] = away_team_avg_for
    if away_team_avg_against:
        away_form["avg_goals_against"] = away_team_avg_against

    # Smart Stats Fallback: enrichir les statistiques manquantes
    events = _response(data["events"])
    estimated_stats = estimate_missing_stats(
        home_stats=home_stats,
        away_stats=away_stats,
        home_form=home_form,
        away_form=away_form,
        home_team_stats=data["home_team_stats"],
        away_team_stats=data["away_team_stats"],
        events=events,
        minute=status.get("elapsed") or 0,
    )
    # Marquer les stats estimées avec astérisque
    original_home_stats = dict(home_stats)
    original_away_stats = dict(away_stats)
    home_stats = mark_estimated(estimated_stats["home"], original_home_stats)
    away_stats = mark_estimated(estimated_stats["away"], original_away_stats)

    home_elo = calculate_elo(home_form, home_advantage=True)
    away_elo = calculate_elo(away_form, home_advantage=False)

    # Build live context for real-time analysis
    current_home_goals = goals.get("home") or 0
    current_away_goals = goals.get("away") or 0
    minute = status.get("elapsed") or 0
    status_short = status.get("short") or "NS"
    events = _response(data["events"])

    live_context = build_live_context(
        home_goals=current_home_goals,
        away_goals=current_away_goals,
        minute=minute,
        status=status_short,
        home_stats=home_stats,
        away_stats=away_stats,
        events=events,
    )

    ai_result = calculate_probabilities(home_form, away_form, home_elo, away_elo, live_context)

    st.markdown("### 🔥 Forme récente")
    col_home, col_away = st.columns(2)
    for col, title, form in [(col_home, home_name, home_form), (col_away, away_name, away_form)]:
        with col:
            st.markdown(f"<div class='analysis-card'><h4>{html_lib.escape(title)}</h4></div>", unsafe_allow_html=True)
            st.metric("Victoires", form["wins"])
            st.metric("Nuls", form["draws"])
            st.metric("Défaites", form["losses"])
            st.metric("Buts marqués", form["goals_for"])
            st.metric("Buts encaissés", form["goals_against"])
            st.metric("Moy. buts marqués", round(form["avg_goals_for"], 2))
            st.metric("Moy. buts encaissés", round(form["avg_goals_against"], 2))
            for row in form["rows"]:
                st.write(f"{row['result']} · {row['opponent']} · {row['score']}")

    st.markdown("### ⚔️ Head to Head")
    h2h_items = _response(data["h2h"])
    if h2h_items:
        for item in h2h_items[:5]:
            item_teams = item.get("teams") or {}
            st.write(f"{(item_teams.get('home') or {}).get('name', '—')} { _fixture_score(item) } {(item_teams.get('away') or {}).get('name', '—')}")
    else:
        st.info("Aucune confrontation directe disponible via l'API.")

    st.markdown("### 🏆 Classement")
    home_standing = _standing_for_team(data["standings"], home_team_id)
    away_standing = _standing_for_team(data["standings"], away_team_id)
    standing_cols = st.columns(2)
    for col, title, row in [(standing_cols[0], home_name, home_standing), (standing_cols[1], away_name, away_standing)]:
        with col:
            st.markdown(f"**{title}**")
            st.metric("Position", row.get("rank", "Non disponible"))
            st.metric("Points", row.get("points", "Non disponible"))
            st.metric("Différence buts", row.get("goalsDiff", "Non disponible"))

    st.markdown("### 🧩 Evénements & lineups")
    events = _response(data["events"])
    lineups = _response(data["lineups"])
    st.write(f"Evénements disponibles : {len(events)}")
    st.write(f"Compositions disponibles : {len(lineups)}")

    st.markdown("### 🤖 Analyse IA intelligente")

    # Afficher le contexte live si disponible
    live_ctx = ai_result.get("live_context")
    if live_ctx and live_ctx.get("is_live"):
        live_cols = st.columns(4)
        live_cols[0].metric("Minute", f"{live_ctx.get('minute', 0)}'")
        live_cols[1].metric("Phase", live_ctx.get("phase", "Inconnu"))
        live_cols[2].metric("État", live_ctx.get("state", "Inconnu"))
        live_cols[3].metric("Momentum", f"{live_ctx.get('momentum', 0):+.0%}")

        # Afficher les statistiques de pression
        pressure_cols = st.columns(2)
        pressure_cols[0].metric(f"Pression {home_name}", f"{live_ctx.get('home_pressure', 0):.0f}")
        pressure_cols[1].metric(f"Pression {away_name}", f"{live_ctx.get('away_pressure', 0):.0f}")

    elo_cols = st.columns(2)
    elo_cols[0].metric(f"Elo {home_name}", home_elo)
    elo_cols[1].metric(f"Elo {away_name}", away_elo)

    st.markdown("### 📈 Probabilités IA")
    probabilities = ai_result["probabilities"]
    prob_cols = st.columns(3)
    prob_cols[0].metric(f"Victoire {home_name}", f"{probabilities['home_win']}%")
    prob_cols[0].progress(probabilities["home_win"] / 100)
    prob_cols[1].metric("Match nul", f"{probabilities['draw']}%")
    prob_cols[1].progress(probabilities["draw"] / 100)
    prob_cols[2].metric(f"Victoire {away_name}", f"{probabilities['away_win']}%")
    prob_cols[2].progress(probabilities["away_win"] / 100)

    st.markdown("### 🎯 Score probable")
    score_cols = st.columns(3)
    for col, score_data in zip(score_cols, ai_result["top_scores"]):
        col.metric(score_data["score"], f"{score_data['probability']}%")

    st.markdown("### 🧠 Niveau confiance IA")
    st.metric(ai_result["confidence_label"], f"{ai_result['confidence']}%")
    st.progress(min(ai_result["confidence"] / 100, 1.0))
    st.caption(
        f"xG local estimé : {ai_result['home_xg']} · xG extérieur estimé : {ai_result['away_xg']}. "
        "Calcul déterministe basé sur les statistiques API, la forme récente, l'attaque, la défense et l'Elo local."
    )

    # ========== 🔥 PARIS SUGGÉRÉS ==========
    st.markdown("---")
    st.markdown("### 🔥 Paris suggérés intelligents")

    # Analyser les opportunités de paris
    bet_analysis = analyze_bet_opportunities(
        live_context=live_context,
        ai_result=ai_result,
        home_form=home_form,
        away_form=away_form,
        home_stats=home_stats,
        away_stats=away_stats,
        events=events,
    )

    # Afficher les suggestions
    suggestions = bet_analysis.get("suggestions", [])
    if suggestions:
        for i, suggestion in enumerate(suggestions[:4], 1):  # Max 4 suggestions
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 3])
                col1.markdown(f"**{i}. {suggestion['bet']}**")
                col1.caption(f"Type: {suggestion['type']}")
                col2.metric("Confiance", f"{suggestion['confidence']:.0f}%")
                col3.caption(f"🧠 {suggestion['logic']}")
                st.progress(suggestion['confidence'] / 100)
                st.markdown("---")
    else:
        st.info("Pas de suggestion de pari assez fiable pour ce match.")

    # Niveau de confiance global
    overall_confidence = bet_analysis.get("confidence_level", "Faible")
    confidence_colors = {
        "Faible": "🔴",
        "Moyen": "🟡",
        "Fort": "🟢",
        "Très fort": "✅",
    }
    st.markdown(
        f"### {confidence_colors.get(overall_confidence, '⚪')} Niveau de confiance global: **{overall_confidence}**"
    )

    # ========== 🧠 CONCLUSION IA FINALE ==========
    st.markdown("---")
    st.markdown("### 🧠 Conclusion IA finale")

    conclusion = bet_analysis.get("conclusion", "Analyse en cours...")
    st.markdown(
        f"<div style='background: linear-gradient(135deg, rgba(0,255,136,0.1), rgba(45,151,245,0.1)); "
        f"padding: 20px; border-radius: 12px; border-left: 4px solid #00ff88;'>"
        f"{conclusion.replace(chr(10), '<br>')}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Note sur les statistiques estimées
    if any("*" in str(v) for v in home_stats.values()) or any("*" in str(v) for v in away_stats.values()):
        st.caption("* Les statistiques marquées d'une astérisque ont été estimées intelligemment par l'IA.")

    # ========== 🎯 PRÉDICTIONS AVANCÉES ==========
    st.markdown("---")
    
    is_live = bool(live_context and live_context.get("minute"))
    
    full_predictions = generate_full_predictions(
        home_team=home_name,
        away_team=away_name,
        expected_home_goals=float(ai_result.get("home_xg", 1.2)),
        expected_away_goals=float(ai_result.get("away_xg", 1.0)),
        home_win_prob=float(ai_result.get("home_win", 0.4)) / 100.0,
        draw_prob=float(ai_result.get("draw", 0.3)) / 100.0,
        away_win_prob=float(ai_result.get("away_win", 0.3)) / 100.0,
        is_live=is_live,
        live_context=live_context if is_live else None,
    )
    render_predictions_section(full_predictions, home_name, away_name)

    st.markdown("</div>", unsafe_allow_html=True)
