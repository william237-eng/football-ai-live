import sqlite3
from pathlib import Path
p = Path(__file__).parent.parent / 'database' / 'betting.db'
try:
    conn = sqlite3.connect(str(p))
    cur = conn.cursor()
    cur.execute("SELECT ticket_id,user_id,points_used,ticket_status,created_at FROM bet_tickets")
    rows = [r for r in cur.fetchall() if r[4] and r[4].startswith('2026-06-02')]
    if not rows:
        print('Aucun ticket trouvé pour la date 2026-06-02 dans la DB.')
    else:
        for r in rows:
            print(r)
    conn.close()
except Exception as e:
    print('Erreur accès DB:', e)

