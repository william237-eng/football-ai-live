"""
ticket_manager.py
=================
Orchestrateur principal : crée un ticket, valide les items, attribue les récompenses.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from modules.betting.ticket_storage import (
    create_ticket, add_bet_item, get_ticket, get_ticket_items,
    update_ticket_status, update_item_result, has_duplicate_ticket,
    init_db, DEFAULT_USER_ID,
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
) -> Dict[str, Any]:
    """
    Valide les sélections, déduit les points et crée le ticket en DB.
    Retourne {success, ticket_id, message}.
    """
    init_db()

    # 1. Valider les sélections
    ok, msg, cleaned = build_ticket_selections(selections)
    if not ok:
        return {"success": False, "ticket_id": None, "message": msg}

    # 2. Vérifier points suffisants
    ok2, msg2 = deduct_points(user_id, amount=5)
    if not ok2:
        return {"success": False, "ticket_id": None, "message": msg2}

    # 3. Anti-doublon
    fids = [s["fixture_id"] for s in cleaned]
    preds = [s["prediction"] for s in cleaned]
    if has_duplicate_ticket(user_id, fids, preds):
        # Rembourser les points
        credit_points(user_id, 5)
        return {"success": False, "ticket_id": None, "message": "Ticket identique déjà actif."}

    # 4. Créer ticket
    ticket_id = create_ticket(user_id, fids, points_used=5)

    # 5. Insérer les items
    for sel in cleaned:
        add_bet_item(
            ticket_id=ticket_id,
            fixture_id=sel["fixture_id"],
            home_team=sel["home_team"],
            away_team=sel["away_team"],
            market=sel["market"],
            prediction=sel["prediction"],
        )

    return {
        "success": True,
        "ticket_id": ticket_id,
        "message": f"Ticket #{ticket_id} créé ! 5 ⭐ débités.",
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

        fixtures_data: Dict[int, Dict] = {}
        events_data:   Dict[int, list] = {}

        for fid in fids:
            try:
                raw, _ = api.get_fixture(fid)
                resp = (raw or {}).get("response") or []
                if resp:
                    obj = resp[0]
                    fixtures_data[fid] = obj
                    events_raw, _ = api.get_events(fid)
                    events_data[fid] = (events_raw or {}).get("response") or []
            except Exception:
                pass

        res = validate_ticket(ticket["ticket_id"], fixtures_data, events_data=events_data, user_id=user_id)
        results.append(res)

    return results
