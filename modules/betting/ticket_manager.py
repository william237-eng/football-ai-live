"""
ticket_manager.py
=================
Orchestrateur principal : crée un ticket, valide les items, attribue les récompenses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from modules.betting.ticket_storage import (
    create_ticket, add_bet_item, get_ticket, get_ticket_items,
    update_ticket_status, update_item_result, has_duplicate_ticket,
    sell_ticket, init_db, DEFAULT_USER_ID,
)
from modules.betting.points_manager import deduct_points, credit_points, get_points_info
from modules.betting.betting_engine import build_ticket_selections
from modules.betting.ticket_validator import check_item, is_finished
from modules.betting.reward_engine import compute_reward


# ─────────────────────────────────────────────────────────────────────────────
# Créer un ticket
# ─────────────────────────────────────────────────────────────────────────────

def submit_ticket(
    selections: List[Dict[str, Any]],
    user_id: int = DEFAULT_USER_ID,
    points_used: int = 5,
) -> Dict[str, Any]:
    """
    Valide les sélections, déduit les points et crée le ticket en DB.
    Retourne {success, ticket_id, message}.
    """
    init_db()
    points_used = max(5, int(points_used))

    # 1. Valider les sélections
    ok, msg, cleaned = build_ticket_selections(selections)
    if not ok:
        return {"success": False, "ticket_id": None, "message": msg}

    # 2. Vérifier points suffisants
    ok2, msg2 = deduct_points(user_id, amount=points_used)
    if not ok2:
        return {"success": False, "ticket_id": None, "message": msg2}

    # 3. Anti-doublon
    fids = [s["fixture_id"] for s in cleaned]
    preds = [s["prediction"] for s in cleaned]
    if has_duplicate_ticket(user_id, fids, preds):
        credit_points(user_id, points_used)
        return {"success": False, "ticket_id": None, "message": "Ticket identique déjà actif."}

    # 4. Créer ticket
    ticket_id = create_ticket(user_id, fids, points_used=points_used)

    # 5. Insérer les items (avec kick_off, odds, live_minute si fournis)
    for sel in cleaned:
        add_bet_item(
            ticket_id=ticket_id,
            fixture_id=sel["fixture_id"],
            home_team=sel["home_team"],
            away_team=sel["away_team"],
            market=sel["market"],
            prediction=sel["prediction"],
            kick_off=sel.get("kick_off", ""),
            odds=float(sel.get("odds", 1.0)),
            live_minute=int(sel.get("live_minute", 0)),
        )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": f"Ticket #{ticket_id} créé ! 5 ⭐ débités.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Vente d'un ticket
# ─────────────────────────────────────────────────────────────────────────────

SELL_PRICE = 4   # points remboursés si vente avant tout match commencé


def compute_ticket_sell_offer(ticket_id: int) -> Dict[str, Any]:
    """
    Calcule si un ticket peut être vendu et à quel prix.
    Règles :
      - Vente pleine (4 pts) : aucun match n'a encore commencé (tous kick_off > now).
      - Vente à moitié du gain potentiel : N-1 événements déjà WON, 1 seul reste PENDING.
      - Impossible si un match a déjà commencé et la vente pleine est demandée.
      - Impossible si statut != ACTIVE.
    Retourne dict {can_sell_full, can_sell_half, sell_price_full, sell_price_half,
                   reason_no_full, reason_no_half, nb_won, nb_total}.
    """
    ticket = get_ticket(ticket_id)
    if not ticket or ticket["ticket_status"] != "ACTIVE":
        return {"can_sell_full": False, "can_sell_half": False,
                "sell_price_full": 0, "sell_price_half": 0,
                "reason_no_full": "Ticket non actif.", "reason_no_half": "Ticket non actif.",
                "nb_won": 0, "nb_total": 0}

    items   = get_ticket_items(ticket_id)
    nb_total = len(items)
    nb_won   = sum(1 for i in items if i["result"] == "WON")
    nb_lost  = sum(1 for i in items if i["result"] == "LOST")
    nb_pending = sum(1 for i in items if i["result"] == "PENDING")

    now_utc = datetime.now(timezone.utc)

    # Vérifier si au moins un match a commencé (live_minute > 0 OU kick_off passé)
    any_started = False
    for item in items:
        if (item.get("live_minute") or 0) > 0:
            any_started = True
            break
        ko = item.get("kick_off", "")
        if ko:
            try:
                ko_dt = datetime.fromisoformat(ko.replace("Z", "+00:00"))
                if ko_dt.astimezone(timezone.utc) <= now_utc:
                    any_started = True
                    break
            except Exception:
                pass

    # Vente pleine : 4 pts, seulement si aucun match n'a commencé
    can_sell_full   = not any_started and nb_lost == 0
    reason_no_full  = ("Impossible : un ou plusieurs matchs ont déjà commencé." if any_started
                       else ("Coupon perdu." if nb_lost > 0 else ""))
    sell_price_full = SELL_PRICE if can_sell_full else 0

    # Vente à moitié du gain potentiel : N-1 WON, 1 PENDING, aucun LOST
    from modules.betting.reward_engine import compute_reward
    reward_info     = compute_reward(ticket["points_used"], nb_total)
    half_price      = max(1, reward_info["reward_points"] // 2)
    can_sell_half   = (nb_won == nb_total - 1 and nb_pending == 1 and nb_lost == 0
                       and any_started)
    reason_no_half  = ("" if can_sell_half
                       else "Disponible quand tous les événements sauf 1 sont validés.")
    sell_price_half = half_price if can_sell_half else 0

    return {
        "can_sell_full":   can_sell_full,
        "can_sell_half":   can_sell_half,
        "sell_price_full": sell_price_full,
        "sell_price_half": sell_price_half,
        "reason_no_full":  reason_no_full,
        "reason_no_half":  reason_no_half,
        "nb_won":          nb_won,
        "nb_total":        nb_total,
        "potential_reward": reward_info["reward_points"],
    }


def sell_ticket_action(
    ticket_id: int,
    mode: str = "full",
    user_id: int = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    """
    Vend un ticket (mode='full' → 4 pts, mode='half' → moitié du gain potentiel).
    Retourne {success, message, points_credited}.
    """
    offer = compute_ticket_sell_offer(ticket_id)
    if mode == "full":
        if not offer["can_sell_full"]:
            return {"success": False, "message": offer["reason_no_full"], "points_credited": 0}
        price = offer["sell_price_full"]
    else:
        if not offer["can_sell_half"]:
            return {"success": False, "message": offer["reason_no_half"], "points_credited": 0}
        price = offer["sell_price_half"]

    sell_ticket(ticket_id, price)
    credit_points(user_id, price)
    return {
        "success": True,
        "message": f"Ticket #{ticket_id} vendu pour {price} ⭐.",
        "points_credited": price,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Valider un ticket (résultat API)
# ─────────────────────────────────────────────────────────────────────────────

def validate_ticket(
    ticket_id: int,
    fixtures_data: Dict[int, Dict],
    stats_data: Optional[Dict[int, Any]] = None,
    events_data: Optional[Dict[int, list]] = None,
    user_id: int = DEFAULT_USER_ID,
) -> Dict[str, Any]:
    """
    Met à jour le résultat de chaque item et statue le ticket.
    fixtures_data: {fixture_id: fixture_dict_brut}
    Retourne le statut final.
    """
    ticket = get_ticket(ticket_id)
    if not ticket:
        return {"success": False, "message": "Ticket introuvable."}
    if ticket["ticket_status"] != "ACTIVE":
        return {"success": True, "status": ticket["ticket_status"], "already_resolved": True}

    items = get_ticket_items(ticket_id)
    all_finished = True
    all_won = True
    lost_reason = ""

    for item in items:
        fid = item["fixture_id"]
        fixture = fixtures_data.get(fid)
        if not fixture:
            all_finished = False
            continue

        if not is_finished(fixture):
            all_finished = False
            continue

        stats  = (stats_data  or {}).get(fid)
        events = (events_data or {}).get(fid)
        if fixture.get("_synthetic"):
            # Fixture synthétique (API indisponible, match passé) → LOST par défaut
            result = "LOST"
        else:
            result = check_item(item["market"], item["prediction"], fixture, stats, events)
        update_item_result(item["id"], result)

        if result == "LOST":
            all_won = False
            lost_reason = f"{item['prediction']} ({item['market']}) échoué"
        elif result == "PENDING":
            all_finished = False

    if not all_finished:
        return {"success": True, "status": "ACTIVE", "message": "Certains matchs non terminés."}

    if all_won:
        nb = len(items)
        reward = compute_reward(ticket["points_used"], nb)
        update_ticket_status(ticket_id, "WON", reward["reward_points"])
        credit_points(user_id, reward["reward_points"])
        return {
            "success": True,
            "status": "WON",
            "reward": reward,
            "message": f"Ticket #{ticket_id} GAGNÉ ! {reward['label']}",
        }
    else:
        update_ticket_status(ticket_id, "LOST", 0)
        return {
            "success": True,
            "status": "LOST",
            "message": f"Ticket #{ticket_id} PERDU. Raison : {lost_reason}",
            "lost_reason": lost_reason,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Vérifier tous les tickets actifs d'un utilisateur
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_fixture_robust(
    api,
    fid: int,
    kick_off_iso: str = "",
    ticket_created_at: str = "",
) -> Optional[Dict]:
    """
    Tente de récupérer un fixture par ID.
    Fallbacks :
      1. get_fixture_detail direct
      2. Si kick_off dépassé de +3h → fixture synthétique FT
      3. Si ticket créé hier ou avant → fixture synthétique FT
    """
    from datetime import datetime, timezone, timedelta

    # 1. Tentative directe
    try:
        raw = api.get_fixture_detail(fid)
        if isinstance(raw, tuple):
            raw = raw[0]
        resp = (raw or {}).get("response") or []
        if resp:
            fx = resp[0]
            # Si l'API renvoie bien le fixture, le retourner même s'il est NS/LIVE
            return fx
    except Exception:
        pass

    now = datetime.now(timezone.utc)

    # 2. Fallback kick_off : si dépassé de +3h
    ref_iso = kick_off_iso or ticket_created_at
    if ref_iso:
        try:
            ref_dt = datetime.fromisoformat(ref_iso.replace("Z", "+00:00"))
            if ref_dt.tzinfo is None:
                ref_dt = ref_dt.replace(tzinfo=timezone.utc)
            if now - ref_dt > timedelta(hours=3):
                return {
                    "fixture": {"id": fid, "status": {"short": "FT", "long": "Match Finished", "elapsed": 90}},
                    "goals":   {"home": None, "away": None},
                    "score":   {},
                    "_synthetic": True,
                }
        except Exception:
            pass

    # 3. Fallback ultime : si le ticket date de plus d'un jour entier
    if ticket_created_at:
        try:
            created_dt = datetime.fromisoformat(ticket_created_at.replace("Z", "+00:00"))
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            if now - created_dt > timedelta(hours=24):
                return {
                    "fixture": {"id": fid, "status": {"short": "FT", "long": "Match Finished", "elapsed": 90}},
                    "goals":   {"home": None, "away": None},
                    "score":   {},
                    "_synthetic": True,
                }
        except Exception:
            pass

    return None


def check_all_active_tickets(
    api,
    user_id: int = DEFAULT_USER_ID,
) -> List[Dict[str, Any]]:
    """
    Parcourt tous les tickets ACTIVE et les valide si les matchs sont terminés.
    api: instance FootballAPI.
    Retourne la liste des résultats de validation.
    """
    from modules.betting.ticket_storage import get_user_tickets

    results = []
    tickets = get_user_tickets(user_id, status="ACTIVE")
    for ticket in tickets:
        items = get_ticket_items(ticket["ticket_id"])
        fids = list({i["fixture_id"] for i in items})

        # Construire un mapping fid → kick_off depuis les items
        kick_offs: Dict[int, str] = {
            i["fixture_id"]: (i.get("kick_off") or i.get("start_datetime_local") or "")
            for i in items
        }

        fixtures_data: Dict[int, Dict] = {}
        events_data:   Dict[int, list] = {}

        ticket_created_at = ticket.get("created_at", "")
        for fid in fids:
            fx = _fetch_fixture_robust(api, fid, kick_offs.get(fid, ""), ticket_created_at)
            if fx:
                fixtures_data[fid] = fx
            try:
                ev_raw = api.get_fixture_events(fid)
                if isinstance(ev_raw, tuple):
                    ev_raw = ev_raw[0]
                events_data[fid] = (ev_raw or {}).get("response") or []
            except Exception:
                events_data[fid] = []

        res = validate_ticket(ticket["ticket_id"], fixtures_data, events_data=events_data, user_id=user_id)
        results.append(res)

    return results
