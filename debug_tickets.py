"""
debug_tickets.py - Script de debug pour vérifier les tickets
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from modules.betting.ticket_storage import init_db, get_user_tickets, get_ticket, get_ticket_items, DEFAULT_USER_ID

def debug_tickets():
    """Debug complet des tickets de l'utilisateur."""
    print("=== DEBUG TICKETS ===")
    
    init_db()
    
    # 1. Vérifier tous les tickets sans filtre
    print("\n1. TOUS les tickets de l'utilisateur:")
    all_tickets = get_user_tickets(DEFAULT_USER_ID)
    print(f"   → Nombre total: {len(all_tickets)}")
    
    for ticket in all_tickets:
        print(f"   Ticket #{ticket['ticket_id']} - Status: {ticket['ticket_status']} - Créé: {ticket.get('created_at', 'N/A')}")
    
    # 2. Vérifier les tickets actifs uniquement
    print("\n2. Tickets ACTIFS uniquement:")
    active_tickets = get_user_tickets(DEFAULT_USER_ID, status="ACTIVE")
    print(f"   → Nombre actifs: {len(active_tickets)}")
    
    for ticket in active_tickets:
        print(f"   Ticket #{ticket['ticket_id']} - Status: {ticket['ticket_status']}")
        
        # Vérifier les items du ticket
        items = get_ticket_items(ticket['ticket_id'])
        print(f"     → Items: {len(items)}")
        for item in items:
            print(f"       • Fixture {item['fixture_id']} - {item['market']} - {item['prediction']} - Result: {item.get('result', 'PENDING')}")
    
    # 3. Vérifier la base de données directement
    print("\n3. Vérification base de données:")
    try:
        from modules.betting.ticket_storage import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Compter tous les tickets
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ?", (DEFAULT_USER_ID,))
        total_count = cursor.fetchone()[0]
        print(f"   → Total tickets en DB: {total_count}")
        
        # Compter les tickets actifs
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ? AND ticket_status = 'ACTIVE'", (DEFAULT_USER_ID,))
        active_count = cursor.fetchone()[0]
        print(f"   → Tickets actifs en DB: {active_count}")
        
        # Lister les tickets avec leurs statuts réels
        cursor.execute("SELECT ticket_id, ticket_status, created_at FROM tickets WHERE user_id = ?", (DEFAULT_USER_ID,))
        db_tickets = cursor.fetchall()
        print(f"   → Tickets en DB:")
        for tid, status, created in db_tickets:
            print(f"     • #{tid} - {status} - {created}")
        
        conn.close()
        
    except Exception as e:
        print(f"   → Erreur DB: {e}")
    
    print("\n=== FIN DEBUG ===")

if __name__ == "__main__":
    debug_tickets()
