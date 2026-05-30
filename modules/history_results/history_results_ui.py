"""
history_results_ui.py
======================
Page HISTORIQUE — matchs terminés du jour ou d'une date sélectionnée.
Calendrier : jusqu'à 14 jours en arrière.
"""
from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List, Optional

import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

FINISHED_STATUSES = {"FT", "AET", "PEN", "ABD", "AWD", "WO"}

COUNTRY_FLAGS = {}  # flag par URL venant de l'API

STATUS_DISPLAY = {
    "FT":  ("⚫ Terminé",        "#888"),
    "AET": ("⚫ Après prolongations", "#888"),
    "PEN": ("⚫ Tirs au but",    "#888"),
    "ABD": ("🚫 Abandonné",      "#ef4444"),
    "AWD": ("🏆 Victoire forfait","#f59e0b"),
    "WO":  ("🚫 Forfait",        "#ef4444"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Fetch résultats d'une date
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_results(api, date_str: str) -> List[Dict[str, Any]]:
    """Récupère et parse tous les matchs terminés d'une date donnée."""
    try:
        raw, _ = api.get_fixtures_by_date(date_str)
    except Exception:
        return []

    results = []
    for fx in raw:
        fixture    = fx.get("fixture") or {}
        teams      = fx.get("teams") or {}
        goals      = fx.get("goals") or {}
        league     = fx.get("league") or {}
        score      = fx.get("score") or {}
        status_inf = fixture.get("status") or {}

        status_short = status_inf.get("short", "NS")
        if status_short not in FINISHED_STATUSES:
            continue

        home = teams.get("home") or {}
        away = teams.get("away") or {}

        home_score = goals.get("home")
        away_score = goals.get("away")

        # Heure
        raw_date = fixture.get("date", "")
        start_time = "—"
        try:
            if raw_date:
                if raw_date.endswith("Z"):
                    raw_date = raw_date[:-1] + "+00:00"
                dtobj = datetime.datetime.fromisoformat(raw_date).astimezone()
                start_time = dtobj.strftime("%H:%M")
        except Exception:
            pass

        # Vainqueur
        winner_id = None
        home_winner = home.get("winner")
        away_winner = away.get("winner")
        if home_winner is True:
            winner_id = home.get("id")
        elif away_winner is True:
            winner_id = away.get("id")

        # Score mi-temps
        ht = score.get("halftime") or {}
        ht_home = ht.get("home")
        ht_away = ht.get("away")
        ht_str = f"{ht_home}-{ht_away}" if ht_home is not None else ""

        results.append({
            "fixture_id":     fixture.get("id"),
            "home_id":        home.get("id"),
            "away_id":        away.get("id"),
            "home_name":      home.get("name", "—"),
            "away_name":      away.get("name", "—"),
            "home_logo":      home.get("logo", ""),
            "away_logo":      away.get("logo", ""),
            "home_score":     home_score,
            "away_score":     away_score,
            "ht_str":         ht_str,
            "winner_id":      winner_id,
            "start_time":     start_time,
            "status_short":   status_short,
            "league_name":    league.get("name", "—"),
            "league_country": league.get("country", "—"),
            "league_flag":    league.get("flag", ""),
            "league_id":      league.get("id"),
        })

    # Tri par heure
    results.sort(key=lambda x: x["start_time"])
    return results


# ─────────────────────────────────────────────────────────────────────────────
# Affichage
# ─────────────────────────────────────────────────────────────────────────────

def _score_color(m: Dict) -> tuple[str, str, str]:
    """Retourne (home_color, away_color, border_color) selon le résultat."""
    hid = m.get("home_id")
    aid = m.get("away_id")
    wid = m.get("winner_id")
    if wid is None:
        return "#f59e0b", "#f59e0b", "#f59e0b"  # nul = orange
    if wid == hid:
        return "#22c55e", "#ef4444", "#22c55e"
    return "#ef4444", "#22c55e", "#22c55e"


def _render_match_row(m: Dict) -> str:
    hs = m["home_score"]
    as_ = m["away_score"]
    score_str = f"{hs} — {as_}" if hs is not None else "— — —"
    ht_str  = f"({m['ht_str']})" if m.get("ht_str") else ""
    h_col, a_col, border = _score_color(m)
    s_label, s_color = STATUS_DISPLAY.get(m["status_short"], ("⚫ Terminé", "#888"))

    # Logos
    def logo(url, name):
        if url:
            return f"<img src='{url}' style='height:20px;width:20px;object-fit:contain;vertical-align:middle;margin:0 4px;' onerror=\"this.style.display='none'\">"
        return f"<span style='font-size:0.8rem;'>{name[:3]}</span>"

    return (
        f"<div style='display:grid;grid-template-columns:1fr 90px 1fr;align-items:center;"
        f"padding:8px 12px;border-radius:10px;margin-bottom:6px;"
        f"background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);"
        f"border-left:3px solid {border};'>"

        # Home
        f"<div style='display:flex;align-items:center;justify-content:flex-end;gap:6px;'>"
        f"<span style='font-size:0.88rem;font-weight:700;color:{h_col};'>{m['home_name']}</span>"
        f"{logo(m['home_logo'], m['home_name'])}"
        f"</div>"

        # Score
        f"<div style='text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:900;letter-spacing:2px;'>{score_str}</div>"
        f"<div style='font-size:0.65rem;color:#666;'>{ht_str}</div>"
        f"<div style='font-size:0.62rem;color:#888;margin-top:2px;'>{m['start_time']}</div>"
        f"</div>"

        # Away
        f"<div style='display:flex;align-items:center;gap:6px;'>"
        f"{logo(m['away_logo'], m['away_name'])}"
        f"<span style='font-size:0.88rem;font-weight:700;color:{a_col};'>{m['away_name']}</span>"
        f"</div>"

        f"</div>"
    )


def _render_league_group(league_name: str, country: str, flag: str, matches: List[Dict]) -> None:
    flag_html = (
        f"<img src='{flag}' style='height:14px;vertical-align:middle;margin-right:6px;'>"
        if flag else ""
    )
    st.markdown(
        f"<div style='background:rgba(255,255,255,0.05);border-radius:10px;"
        f"padding:10px 14px;margin-bottom:4px;'>"
        f"<div style='font-size:0.78rem;font-weight:700;color:#ccc;margin-bottom:8px;'>"
        f"{flag_html}{league_name} · <span style='color:#888;font-weight:400;'>{country}</span>"
        f"</div>"
        + "".join(_render_match_row(m) for m in matches)
        + "</div>",
        unsafe_allow_html=True,
    )


def _group_by_league(matches: List[Dict]) -> Dict[str, List[Dict]]:
    grouped: Dict[str, List] = {}
    for m in matches:
        key = f"{m['league_id']}_{m['league_name']}"
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(m)
    return grouped


def _render_stats_bar(matches: List[Dict]) -> None:
    total    = len(matches)
    home_w   = sum(1 for m in matches if m["winner_id"] and m["winner_id"] == m["home_id"])
    draws    = sum(1 for m in matches if m["winner_id"] is None and m["home_score"] is not None)
    away_w   = sum(1 for m in matches if m["winner_id"] and m["winner_id"] == m["away_id"])
    total_g  = sum(
        (m["home_score"] or 0) + (m["away_score"] or 0)
        for m in matches if m["home_score"] is not None
    )
    avg_g    = round(total_g / total, 2) if total > 0 else 0
    over25   = sum(
        1 for m in matches
        if m["home_score"] is not None and (m["home_score"] + m["away_score"]) >= 3
    )

    html = (
        f"<div style='display:grid;grid-template-columns:repeat(6,1fr);"
        f"gap:6px;margin-bottom:14px;'>"

        f"<div style='background:rgba(255,255,255,0.04);border-radius:8px;"
        f"padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:800;'>{total}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Matchs</div></div>"

        f"<div style='background:rgba(34,197,94,0.1);border-radius:8px;"
        f"padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#22c55e;'>{home_w}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Domicile</div></div>"

        f"<div style='background:rgba(245,158,11,0.1);border-radius:8px;"
        f"padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#f59e0b;'>{draws}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Nuls</div></div>"

        f"<div style='background:rgba(59,130,246,0.1);border-radius:8px;"
        f"padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#3b82f6;'>{away_w}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Extérieur</div></div>"

        f"<div style='background:rgba(0,212,255,0.08);border-radius:8px;"
        f"padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#00d4ff;'>{avg_g}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Moy. buts</div></div>"

        f"<div style='background:rgba(167,139,250,0.1);border-radius:8px;"
        f"padding:8px;text-align:center;'>"
        f"<div style='font-size:1.1rem;font-weight:800;color:#a78bfa;'>{over25}</div>"
        f"<div style='font-size:0.65rem;color:#888;'>Over 2.5</div></div>"

        f"</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Recherche
# ─────────────────────────────────────────────────────────────────────────────

def _filter_matches(matches: List[Dict], query: str) -> List[Dict]:
    if not query or not query.strip():
        return matches
    q = query.strip().lower()
    return [
        m for m in matches
        if q in m["home_name"].lower()
        or q in m["away_name"].lower()
        or q in m["league_name"].lower()
        or q in m["league_country"].lower()
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────────────────────

def render_history_page(api) -> None:
    """Page HISTORIQUE — matchs terminés avec sélection de date."""

    today = datetime.date.today()
    min_date = today - datetime.timedelta(days=14)

    st.markdown(
        "<h2 style='font-size:1.6rem;margin-bottom:2px;'>📅 HISTORIQUE DES MATCHS</h2>"
        "<p style='color:#888;font-size:0.85rem;margin-bottom:14px;'>"
        "Résultats des matchs terminés · Sélectionnez une date (jusqu'à 14 jours en arrière)</p>",
        unsafe_allow_html=True,
    )

    # ── Raccourcis rapides — AVANT le widget pour initialiser la date ─────
    # On utilise "history_date_sel" (clé interne) distincte de la clé du widget.
    # Les raccourcis écrivent dans "history_date_sel" AVANT que le widget soit créé.
    if "history_date_sel" not in st.session_state:
        st.session_state["history_date_sel"] = today

    shortcut_cols = st.columns(5)
    shortcuts = [
        ("Aujourd'hui", 0),
        ("Hier",        1),
        ("Il y a 2j",   2),
        ("Il y a 3j",   3),
        ("Il y a 7j",   7),
    ]
    for i, (label, delta) in enumerate(shortcuts):
        with shortcut_cols[i]:
            target = today - datetime.timedelta(days=delta)
            is_active = (st.session_state["history_date_sel"] == target)
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"hist_sc_{delta}",
                         use_container_width=True, type=btn_type):
                st.session_state["history_date_sel"] = target
                st.rerun()

    # ── Sélecteur de date + recherche ─────────────────────────────────────
    col_date, col_search, col_refresh = st.columns([2, 2, 1])

    with col_date:
        # Le widget n'a PAS de key pour éviter le conflit ; on lit sa valeur directement.
        selected_date = st.date_input(
            "Date",
            value=st.session_state["history_date_sel"],
            min_value=min_date,
            max_value=today,
            label_visibility="collapsed",
            format="DD/MM/YYYY",
        )
        # Synchroniser la sélection manuelle vers la clé interne
        if selected_date != st.session_state["history_date_sel"]:
            st.session_state["history_date_sel"] = selected_date

    with col_search:
        search_q = st.text_input(
            "Recherche",
            placeholder="🔍 Équipe, ligue, pays…",
            key="history_search",
            label_visibility="collapsed",
        )

    with col_refresh:
        force_refresh = st.button("🔄", use_container_width=True, key="history_refresh",
                                  help="Actualiser")

    # ── Cache ─────────────────────────────────────────────────────────────
    date_str     = selected_date.isoformat()
    date_display = selected_date.strftime("%A %d %B %Y").capitalize()
    cache_key    = f"history_results_{date_str}"
    ts_key       = f"history_ts_{date_str}"

    now_ts    = time.time()
    CACHE_TTL = 120  # 2 min pour les données du jour, 1h pour les anciennes
    if selected_date < today:
        CACHE_TTL = 3600

    cached  = st.session_state.get(cache_key)
    last_ts = st.session_state.get(ts_key, 0)
    need_fetch = (cached is None or force_refresh or (now_ts - last_ts) > CACHE_TTL)

    if need_fetch:
        with st.spinner(f"Chargement des résultats du {date_display}…"):
            matches = _fetch_results(api, date_str)
        st.session_state[cache_key] = matches
        st.session_state[ts_key]    = now_ts
    else:
        matches = cached or []

    # ── Timestamp ─────────────────────────────────────────────────────────
    import datetime as _dt
    ts = st.session_state.get(ts_key, now_ts)
    dt_str = _dt.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
    is_today_selected = (selected_date == today)
    cache_info = "2 min" if is_today_selected else "1 h"
    st.caption(
        f"📅 {date_display} · {len(matches)} match(s) terminé(s) · "
        f"Màj : {dt_str} · Cache : {cache_info}"
    )

    # ── Filtre recherche ──────────────────────────────────────────────────
    filtered = _filter_matches(matches, search_q)

    if not filtered:
        if not matches:
            st.info(
                f"Aucun match terminé trouvé pour le {date_display}. "
                f"{'Les matchs se mettront à jour automatiquement.' if is_today_selected else 'Vérifiez la date sélectionnée.'}"
            )
        else:
            st.warning(f"Aucun match ne correspond à « {search_q} ».")
        return

    # ── Statistiques du jour ──────────────────────────────────────────────
    _render_stats_bar(filtered)

    # ── Groupement par ligue ──────────────────────────────────────────────
    grouped = _group_by_league(filtered)

    # Trier les ligues par nb de matchs décroissant, puis nom
    league_order = sorted(
        grouped.keys(),
        key=lambda k: (-len(grouped[k]), k)
    )

    for key in league_order:
        league_matches = grouped[key]
        sample = league_matches[0]
        _render_league_group(
            sample["league_name"],
            sample["league_country"],
            sample["league_flag"],
            league_matches,
        )
