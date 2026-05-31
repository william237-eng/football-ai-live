"""
under25_monitor.py
==================
Fetch + calcul Under 2.5 — même stratégie 2 passes que Over 2.5.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Tuple

from modules.top_under25_live.under25_engine import compute_under25_probability, MIN_UNDER_PROB
from modules.top_over25_live.league_blacklist import is_blacklisted

MAX_ACTIVE   = 10
MAX_RESOLVED = 15
MAX_ENRICH   = 15


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
    home_recent = away_recent = h2h = []
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
    """Valide le résultat Under 2.5 : total buts <= 2 → VALIDATED."""
    total = m.get("home_score", 0) + m.get("away_score", 0)
    if total <= 2:
        m["validation"] = {
            "result":  "VALIDATED",
            "label":   "✅ UNDER 2.5 VALIDÉ",
            "reason":  f"{total} but(s) — Under 2.5 confirmé",
            "color":   "#22c55e",
            "border":  "#22c55e",
            "bg":      "rgba(34,197,94,0.10)",
        }
    else:
        m["validation"] = {
            "result":  "FAILED",
            "label":   "❌ OVER 2.5 — Échec",
            "reason":  f"{total} buts — Under 2.5 raté",
            "color":   "#ef4444",
            "border":  "#ef4444",
            "bg":      "rgba(239,68,68,0.10)",
        }
    return m


def fetch_top_under25(api, continent_filter: str = "Tous") -> List[Dict[str, Any]]:
    """
    Stratégie 2 passes :
      Passe 1 — calcul rapide local pour pré-filtrer
      Passe 2 — enrichissement API uniquement sur les TOP candidats
    """
    today_str = date.today().isoformat()
    raw_items: List[Dict] = []
    seen_ids: set = set()

    try:
        raw_today, _ = api.get_fixtures_by_date(today_str)
        for fx in _parse(raw_today):
            fid = (fx.get("fixture") or {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                raw_items.append(fx)
    except Exception:
        pass

    try:
        raw_live, _ = api.get_live_matches()
        for fx in _parse(raw_live):
            fid = (fx.get("fixture") or {}).get("id")
            if fid and fid not in seen_ids:
                seen_ids.add(fid)
                raw_items.append(fx)
    except Exception:
        pass

    if not raw_items:
        return []

    # ── Passe 1 : calcul rapide, 0 appel externe ─────────────────────────
    pre_active:   List[tuple] = []
    pre_resolved: List[tuple] = []

    for fx in raw_items:
        status_short = (fx.get("fixture") or {}).get("status", {}).get("short", "NS")
        if status_short in ("CANC", "ABD", "AWD", "WO", "TBD"):
            continue
        if is_blacklisted(fx):
            continue

        try:
            quick = compute_under25_probability(fixture_raw=fx)
        except Exception:
            continue

        if continent_filter != "Tous" and quick["continent"] != continent_filter:
            continue

        is_fin  = quick["is_finished"]
        total_g = quick["home_score"] + quick["away_score"]
        prob    = quick["under25_prob"]
        minute  = quick["minute"]

        if is_fin:
            if prob >= MIN_UNDER_PROB or total_g <= 2:
                pre_resolved.append((prob, fx, status_short))
        elif total_g >= 3:
            # Déjà Over → Under impossible, on enregistre comme résolu échoué
            pre_resolved.append((0.0, fx, status_short))
        elif minute <= 70 and prob >= MIN_UNDER_PROB:
            pre_active.append((prob, fx, status_short))

    pre_active.sort(key=lambda x: x[0], reverse=True)
    top_active   = pre_active[:MAX_ENRICH]
    top_resolved = pre_resolved[:MAX_RESOLVED]

    # ── Passe 2 : enrichissement API ciblé ───────────────────────────────
    active_candidates:   List[Dict] = []
    resolved_candidates: List[Dict] = []

    for (_, fx, status_short) in top_active + top_resolved:
        home_recent, away_recent, h2h = _fetch_real_stats(api, fx)

        live_stats = None
        fid = (fx.get("fixture") or {}).get("id")
        if status_short in ("1H", "2H", "HT", "ET", "BT", "P", "LIVE") and fid:
            try:
                raw_stats = api.get_fixture_statistics(fid)
                live_stats = _safe_resp(raw_stats) or None
            except Exception:
                pass

        try:
            m = compute_under25_probability(
                fixture_raw=fx,
                home_recent=home_recent or None,
                away_recent=away_recent or None,
                h2h_fixtures=h2h or None,
                live_stats=live_stats,
            )
            m["_home_recent"] = home_recent
            m["_away_recent"] = away_recent
            m["_h2h"]         = h2h
        except Exception:
            continue

        is_fin  = m["is_finished"]
        total_g = m["home_score"] + m["away_score"]
        prob    = m["under25_prob"]
        minute  = m["minute"]

        if is_fin:
            m = _validate_under25(m)
            if prob >= MIN_UNDER_PROB or total_g <= 2:
                resolved_candidates.append(m)
        elif total_g >= 3:
            m = _validate_under25(m)
            resolved_candidates.append(m)
        else:
            if prob >= MIN_UNDER_PROB:
                active_candidates.append(m)

    active_candidates.sort(key=lambda x: x["under25_prob"], reverse=True)
    resolved_candidates.sort(
        key=lambda x: (
            1 if (x.get("validation") or {}).get("result") == "VALIDATED" else 0,
            -(x["home_score"] + x["away_score"]),
        ),
        reverse=True,
    )

    return active_candidates[:MAX_ACTIVE] + resolved_candidates[:MAX_RESOLVED]


def categorize_matches(matches: List[Dict]) -> Dict[str, List[Dict]]:
    active = validated = failed = []
    active, validated, failed = [], [], []
    for m in matches:
        is_fin  = m.get("is_finished", False)
        total_g = m.get("home_score", 0) + m.get("away_score", 0)
        val     = m.get("validation") or {}
        locked  = m.get("locked", False)

        if is_fin:
            if val.get("result") == "VALIDATED":
                validated.append(m)
            else:
                failed.append(m)
        elif locked and total_g >= 3:
            failed.append(m)
        else:
            active.append(m)

    return {"active": active, "validated": validated, "failed": failed}


def refresh_live_matches(api, current_matches: List[Dict]) -> List[Dict]:
    updated = []
    for m in current_matches:
        fid = m.get("fixture_id")
        if not fid or m.get("is_finished"):
            updated.append(m)
            continue
        try:
            raw   = api.get_fixture_detail(fid)
            items = _parse(raw)
            if not items:
                updated.append(m)
                continue
            fresh_fx = items[0]

            live_stats = None
            try:
                raw_stats  = api.get_fixture_statistics(fid)
                live_stats = _safe_resp(raw_stats) or None
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
            refreshed["initial_prob"]  = m.get("initial_prob", refreshed["under25_prob"])
            refreshed["initial_pct"]   = m.get("initial_pct",  refreshed["under25_pct"])
            refreshed["_home_recent"]  = home_recent
            refreshed["_away_recent"]  = away_recent
            refreshed["_h2h"]          = h2h_fixtures
            m = refreshed
        except Exception:
            pass
        updated.append(m)
    return updated
