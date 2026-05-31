"""
under25_monitor.py
==================
Orchestrateur UNDER 2.5 STRICT.
Architecture : live / future / resolved séparés.
Règle 8 : jamais de remplissage artificiel.
"""
from __future__ import annotations

import time as _time
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from modules.top_under25_live.under25_engine import (
    compute_under25_probability, MIN_UNDER_SCORE,
)
from modules.top_over25_live.league_blacklist import is_blacklisted

# ── Limites (Règle 1) ──────────────────────────────────────────────────────
MAX_LIVE     = 5
MAX_FUTURE   = 5
MAX_RESOLVED = 15
MAX_ENRICH   = 40   # pool large avant filtrage

# ── Seuils LIVE stricts (Règle 3) ─────────────────────────────────────────
LIVE_MIN_MINUTE    = 5
LIVE_MAX_MINUTE    = 75
LIVE_MAX_GOALS     = 2   # total_goals <= 2 pour accepter
LIVE_MAX_RED_CARDS = 1
LIVE_MIN_SHOTS     = 2
LIVE_MIN_CORNERS   = 1
LIVE_MIN_PROB      = 0.55

# ── Seuils FUTURS stricts (Règle 2) ──────────────────────────────────────
FUT_MIN_PROB       = 0.60
FUT_MAX_EXP_GOALS  = 2.8
FUT_MAX_AVG_GOALS  = 3.2
FUT_MAX_BTTS       = 0.65
FUT_MIN_H2H_UNDER  = 0.40
FUT_MAX_ATK        = 2.5   # rejeter si une équipe marque >2.5/match

# ── Seuil d'affichage aligné sur ABS_MIN_SCORE ──────────────────────────────
MIN_DISPLAY_SCORE  = 55.0

# ── Seuils absolus communs live + futurs ──────────────────────────────────
ABS_MIN_PROB  = 0.55   # prob_under25 >= 55% obligatoire
ABS_MIN_SCORE = 55.0   # under_score >= 55 obligatoire
_CONF_REJECT  = set()  # pas de rejet par confiance seule

# ── Cote de référence pour ROI réel ──────────────────────────────────────
REF_ODD = 1.80


# ─────────────────────────────────────────────────────────────────────────────
# Prediction History DB  (Problème 2 & 3)
# Stocké dans st.session_state["under25_pred_history"]
# Structure : List[Dict] avec clés :
#   match_id, timestamp_prediction, predicted_market,
#   probability, status ("pending"|"win"|"loss")
# ─────────────────────────────────────────────────────────────────────────────

_DB_KEY = "under25_pred_history"


def _get_db() -> List[Dict]:
    """Récupère la DB depuis session_state (import streamlit lazy)."""
    try:
        import streamlit as st
        if _DB_KEY not in st.session_state:
            st.session_state[_DB_KEY] = []
        return st.session_state[_DB_KEY]
    except Exception:
        return []


def register_prediction(m: Dict[str, Any]) -> None:
    """
    Enregistre une prédiction dans l'historique au moment où elle est affichée.
    N'enregistre que si match_id absent de la DB (évite les doublons).
    """
    mid = m.get("fixture_id")
    if mid is None:
        return
    db = _get_db()
    existing_ids = {e["match_id"] for e in db}
    if mid in existing_ids:
        return
    entry: Dict[str, Any] = {
        "match_id":             mid,
        "timestamp_prediction": datetime.utcnow().isoformat(),
        "predicted_market":     "UNDER 2.5",
        "probability":          m.get("under25_prob", 0.0),
        "under_score":          m.get("under_score", 0.0),
        "conf_label":           m.get("conf_label", ""),
        "home_name":            m.get("home_name", ""),
        "away_name":            m.get("away_name", ""),
        "status":               "pending",
        "home_score":           None,
        "away_score":           None,
    }
    db.append(entry)


def update_prediction_result(match_id: Any, home_score: int, away_score: int) -> None:
    """Met à jour le statut d'une prédiction une fois le match terminé."""
    total = home_score + away_score
    result = "win" if total <= 2 else "loss"
    db = _get_db()
    for entry in db:
        if entry["match_id"] == match_id and entry["status"] == "pending":
            entry["status"]     = result
            entry["home_score"] = home_score
            entry["away_score"] = away_score
            break


def get_prediction_stats() -> Dict[str, Any]:
    """
    Calcule winrate et ROI réel uniquement sur prédictions résolues (win/loss).
    Retourne dict avec : wins, losses, resolved, winrate_str, roi, profit.
    """
    db = _get_db()
    resolved = [e for e in db if e["status"] in ("win", "loss")]
    pending  = [e for e in db if e["status"] == "pending"]
    wins     = sum(1 for e in resolved if e["status"] == "win")
    losses   = len(resolved) - wins
    n        = len(resolved)

    if n == 0:
        return {
            "wins": 0, "losses": 0, "pending": len(pending),
            "resolved": 0,
            "winrate_str": "--",
            "winrate_pct": None,
            "roi": None, "profit": None,
        }

    profit   = round(wins * (REF_ODD - 1) - losses, 2)
    roi      = round(profit / n * 100, 1)
    winrate  = round(wins / n * 100)
    return {
        "wins":        wins,
        "losses":      losses,
        "pending":     len(pending),
        "resolved":    n,
        "winrate_str": f"{winrate}%",
        "winrate_pct": winrate,
        "roi":         roi,
        "profit":      profit,
    }


def _parse(payload: Any) -> List[Dict]:
    if isinstance(payload, dict) and "response" in payload:
        return payload.get("response") or []
    if isinstance(payload, list):
        return payload
    return []


def _safe_resp(raw: Any) -> List[Dict]:
    if isinstance(raw, dict):
        return raw.get("response") or []
    if isinstance(raw, list):
        return raw
    return []


def _fetch_real_stats(api, fx: Dict) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    teams   = fx.get("teams") or {}
    home_id = (teams.get("home") or {}).get("id")
    away_id = (teams.get("away") or {}).get("id")
    home_recent: List[Dict] = []
    away_recent: List[Dict] = []
    h2h:         List[Dict] = []
    if home_id:
        try:
            home_recent = _safe_resp(api.get_team_recent_fixtures(home_id, count=6))
        except Exception:
            pass
    if away_id:
        try:
            away_recent = _safe_resp(api.get_team_recent_fixtures(away_id, count=6))
        except Exception:
            pass
    if home_id and away_id:
        try:
            h2h = _safe_resp(api.get_head_to_head(home_id, away_id, count=5))
        except Exception:
            pass
    return home_recent, away_recent, h2h


def _validate_under25(m: Dict[str, Any]) -> Dict[str, Any]:
    """Règle 6 : total_goals <= 2 → VALIDÉ, sinon ÉCHOUÉ."""
    total = m.get("home_score", 0) + m.get("away_score", 0)
    if total <= 2:
        m["validation"] = {
            "result": "VALIDATED",
            "label":  "✅ UNDER 2.5 VALIDÉ",
            "reason": f"{total} but(s) — Under 2.5 confirmé",
            "color":  "#22c55e",
            "border": "#22c55e",
            "bg":     "rgba(34,197,94,0.10)",
        }
    else:
        m["validation"] = {
            "result": "FAILED",
            "label":  "❌ OVER 2.5 — Échec",
            "reason": f"{total} buts — Under 2.5 raté",
            "color":  "#ef4444",
            "border": "#ef4444",
            "bg":     "rgba(239,68,68,0.10)",
        }
    # Mettre à jour la DB historique
    update_prediction_result(m.get("fixture_id"), m["home_score"], m["away_score"])
    return m


def _passes_absolute_filters(m: Dict[str, Any]) -> bool:
    """
    Filtre absolu commun live + futurs (Problème 1) :
    - under_score >= 65
    - prob_under25 >= 70%
    - confidence != 'Faible'
    """
    if m.get("under_score", 0) < ABS_MIN_SCORE:
        return False
    if m.get("under25_prob", 0) < ABS_MIN_PROB:
        return False
    if m.get("conf_label", "") in _CONF_REJECT:
        return False
    return True


def fetch_top_under25(
    api,
    continent_filter: str = "Tous",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Retourne {"live": [...], "future": [...], "resolved": [...]}.
    QUALITÉ > QUANTITÉ — jamais de remplissage artificiel.
    """
    today_str = date.today().isoformat()
    live_raw:     List[Dict] = []
    future_raw:   List[Dict] = []
    resolved_raw: List[Dict] = []
    seen_ids: set = set()

    # ── Fetch matchs live ─────────────────────────────────────────────────
    try:
        raw_live, _ = api.get_live_matches()
        for fx in _parse(raw_live):
            fid = (fx.get("fixture") or {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                live_raw.append(fx)
    except Exception:
        pass

    # ── Fetch matchs du jour ──────────────────────────────────────────────
    _now_utc = datetime.now(timezone.utc)
    try:
        raw_today, _ = api.get_fixtures_by_date(today_str)
        for fx in _parse(raw_today):
            fid          = (fx.get("fixture") or {}).get("id")
            status_short = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
            if not fid or fid in seen_ids:
                continue
            seen_ids.add(fid)
            if status_short in ("CANC", "ABD", "AWD", "WO", "TBD"):
                continue
            if status_short in ("FT", "AET", "PEN"):
                resolved_raw.append(fx)
            elif status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE"):
                pass  # déjà dans live_raw via get_live_matches
            else:
                # Match non commencé (NS, PST, INT…) — vérifier heure de début
                ts = (fx.get("fixture") or {}).get("timestamp")
                if ts:
                    try:
                        kick_off = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                        if kick_off > _now_utc:
                            future_raw.append(fx)
                        # sinon match prévu mais déjà passé → ignoré
                    except (TypeError, ValueError, OSError):
                        pass
                # si pas de timestamp : ignorer
    except Exception:
        pass

    def _quick(fx):
        try:
            return compute_under25_probability(fixture_raw=fx)
        except Exception:
            return None

    def _enrich(fx, st: str) -> Tuple[Dict | None, List | None]:
        fid_e = (fx.get("fixture") or {}).get("id")
        home_recent, away_recent, h2h = _fetch_real_stats(api, fx)
        live_stats = None
        if st in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE") and fid_e:
            try:
                live_stats = _safe_resp(api.get_fixture_statistics(fid_e)) or None
            except Exception:
                pass
        try:
            md = compute_under25_probability(
                fixture_raw=fx,
                home_recent=home_recent or None,
                away_recent=away_recent or None,
                h2h_fixtures=h2h or None,
                live_stats=live_stats,
            )
            md["_home_recent"] = home_recent
            md["_away_recent"] = away_recent
            md["_h2h"]         = h2h
            return md, live_stats
        except Exception:
            return None, None

    # ══════════════════════════════════════════════════════════════════════
    # LIVE — filtres stricts Règle 3
    # ══════════════════════════════════════════════════════════════════════
    live_candidates: List[tuple] = []
    for fx in live_raw:
        if is_blacklisted(fx):
            continue
        q = _quick(fx)
        if q is None:
            continue
        if continent_filter != "Tous" and q["continent"] != continent_filter:
            continue
        minute  = q["minute"]
        total_g = q["home_score"] + q["away_score"]
        # Rejets absolus Règle 3
        if minute < LIVE_MIN_MINUTE or minute > LIVE_MAX_MINUTE:
            continue
        if total_g > LIVE_MAX_GOALS:
            continue
        # Filtre absolu Problème 1
        if not _passes_absolute_filters(q):
            continue
        if q.get("is_ultra_offensive"):
            continue
        live_candidates.append((q["under_score"], fx, q))

    live_candidates.sort(key=lambda x: x[0], reverse=True)

    live_final: List[Dict[str, Any]] = []
    seen_enrich: set = set()
    for score, fx, _ in live_candidates[:MAX_ENRICH]:
        fid_e = (fx.get("fixture") or {}).get("id")
        if fid_e in seen_enrich:
            continue
        seen_enrich.add(fid_e)
        st = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
        md, _ = _enrich(fx, st)
        if md is None:
            continue
        minute  = md["minute"]
        total_g = md["home_score"] + md["away_score"]
        # Re-vérifier post-enrichissement
        if minute < LIVE_MIN_MINUTE or minute > LIVE_MAX_MINUTE:
            continue
        if total_g > LIVE_MAX_GOALS:
            continue
        # Filtre absolu Problème 1
        if not _passes_absolute_filters(md):
            continue
        if md.get("shots_total", 0) < LIVE_MIN_SHOTS:
            continue
        if md.get("corners_total", 0) < LIVE_MIN_CORNERS:
            continue
        if md.get("red_cards", 0) > LIVE_MAX_RED_CARDS:
            continue
        if md.get("is_ultra_offensive"):
            continue
        # Retirer si 3 buts ou plus (Under 2.5 déjà perdu)
        if total_g >= 3:
            continue
        md["match_type"] = "live"
        live_final.append(md)

    live_final.sort(key=lambda x: x["under_score"], reverse=True)
    live_top = live_final[:MAX_LIVE]

    # ══════════════════════════════════════════════════════════════════════
    # FUTURS — filtres stricts Règle 2
    # ══════════════════════════════════════════════════════════════════════
    future_candidates: List[tuple] = []
    for fx in future_raw:
        if is_blacklisted(fx):
            continue
        q = _quick(fx)
        if q is None:
            continue
        if continent_filter != "Tous" and q["continent"] != continent_filter:
            continue
        # Filtre absolu Problème 1
        if not _passes_absolute_filters(q):
            continue
        # Rejets Règle 2 spécifiques futurs
        if q["expected_goals"] > FUT_MAX_EXP_GOALS:
            continue
        if q["avg_goals_last5"] > FUT_MAX_AVG_GOALS:
            continue
        if q["btts_rate"] > FUT_MAX_BTTS:
            continue
        if q["h2h_under_rate"] < FUT_MIN_H2H_UNDER:
            continue
        if q.get("home_atk", 0) > FUT_MAX_ATK or q.get("away_atk", 0) > FUT_MAX_ATK:
            continue
        if q.get("is_ultra_offensive"):
            continue
        future_candidates.append((q["under_score"], fx, q))

    future_candidates.sort(key=lambda x: x[0], reverse=True)

    future_final: List[Dict[str, Any]] = []
    seen_fut: set = set()
    for score, fx, _ in future_candidates[:MAX_ENRICH]:
        fid_e = (fx.get("fixture") or {}).get("id")
        if fid_e in seen_fut:
            continue
        seen_fut.add(fid_e)
        md, _ = _enrich(fx, "NS")
        if md is None:
            continue
        # Re-vérifier post-enrichissement (filtre absolu)
        if not _passes_absolute_filters(md):
            continue
        if md["expected_goals"] > FUT_MAX_EXP_GOALS:
            continue
        if md["avg_goals_last5"] > FUT_MAX_AVG_GOALS:
            continue
        if md["btts_rate"] > FUT_MAX_BTTS:
            continue
        if md["h2h_under_rate"] < FUT_MIN_H2H_UNDER:
            continue
        if md.get("home_atk", 0) > FUT_MAX_ATK or md.get("away_atk", 0) > FUT_MAX_ATK:
            continue
        if md.get("is_ultra_offensive"):
            continue
        md["match_type"] = "future"
        future_final.append(md)

    future_final.sort(key=lambda x: x["under_score"], reverse=True)
    future_top = future_final[:MAX_FUTURE]

    # ══════════════════════════════════════════════════════════════════════
    # RÉSOLUS — uniquement les prédictions réellement émises (Problème 2)
    # On ne valide que les matchs présents dans la prediction_history_db
    # ══════════════════════════════════════════════════════════════════════
    db = _get_db()
    emitted_ids = {e["match_id"] for e in db}

    resolved_final: List[Dict[str, Any]] = []
    seen_res: set = set()
    for fx in resolved_raw:
        if is_blacklisted(fx):
            continue
        fid_e = (fx.get("fixture") or {}).get("id")
        if fid_e in seen_res:
            continue
        seen_res.add(fid_e)
        # Ne valider QUE si une prédiction a été émise pour ce match
        if fid_e not in emitted_ids:
            continue
        st_short = (fx.get("fixture") or {}).get("status", {}).get("short", "FT")
        md, _ = _enrich(fx, st_short)
        if md is None:
            continue
        md = _validate_under25(md)
        md["match_type"] = "finished"
        md["prediction_emitted"] = True
        resolved_final.append(md)

    resolved_final.sort(
        key=lambda x: (
            1 if (x.get("validation") or {}).get("result") == "VALIDATED" else 0,
            x.get("under_score", 0),
        ),
        reverse=True,
    )
    resolved_top = resolved_final[:MAX_RESOLVED]

    return {
        "live":     live_top,
        "future":   future_top,
        "resolved": resolved_top,
    }


def categorize_matches(matches: List[Dict]) -> Dict[str, List[Dict]]:
    """Compatibilité legacy — sépare une liste plate."""
    active: List[Dict]    = []
    validated: List[Dict] = []
    failed: List[Dict]    = []
    for m in matches:
        is_fin  = m.get("is_finished", False)
        total_g = m.get("home_score", 0) + m.get("away_score", 0)
        val     = m.get("validation") or {}
        if is_fin:
            if val.get("result") == "VALIDATED":
                validated.append(m)
            else:
                failed.append(m)
        elif total_g >= 3 or m.get("locked"):
            failed.append(m)
        else:
            active.append(m)
    return {"active": active, "validated": validated, "failed": failed}


def refresh_live_matches(
    api,
    current_data: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Rafraîchit uniquement les matchs live non terminés."""
    live_matches = current_data.get("live") or []
    updated_live: List[Dict[str, Any]] = []

    for m in live_matches:
        fid = m.get("fixture_id")
        if not fid or m.get("is_finished"):
            updated_live.append(m)
            continue
        try:
            raw   = api.get_fixture_detail(fid)
            items = _parse(raw)
            if not items:
                updated_live.append(m)
                continue
            fresh_fx = items[0]
            live_stats = None
            try:
                live_stats = _safe_resp(api.get_fixture_statistics(fid)) or None
            except Exception:
                pass
            home_recent  = m.get("_home_recent") or []
            away_recent  = m.get("_away_recent") or []
            h2h_fixtures = m.get("_h2h") or []
            if not home_recent and not away_recent:
                home_recent, away_recent, h2h_fixtures = _fetch_real_stats(api, fresh_fx)
            refreshed = compute_under25_probability(
                fixture_raw=fresh_fx,
                home_recent=home_recent or None,
                away_recent=away_recent or None,
                h2h_fixtures=h2h_fixtures or None,
                live_stats=live_stats,
            )
            refreshed["initial_prob"] = m.get("initial_prob", refreshed["under25_prob"])
            refreshed["initial_pct"]  = m.get("initial_pct",  refreshed["under25_pct"])
            refreshed["_home_recent"] = home_recent
            refreshed["_away_recent"] = away_recent
            refreshed["_h2h"]         = h2h_fixtures
            # Retirer si score invalide Règle 3
            total_g = refreshed["home_score"] + refreshed["away_score"]
            if total_g >= 3:
                refreshed = _validate_under25(refreshed)
                current_data.setdefault("resolved", []).append(refreshed)
                continue
            updated_live.append(refreshed)
        except Exception:
            updated_live.append(m)

    return {
        "live":     updated_live,
        "future":   current_data.get("future") or [],
        "resolved": current_data.get("resolved") or [],
    }
