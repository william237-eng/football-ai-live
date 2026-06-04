import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from services.football_api import FootballAPI
from modules.betting.ticket_manager import check_all_active_tickets

api = FootballAPI()
print('API configured:', api.is_configured())
try:
    results = check_all_active_tickets(api)
    print('Résultats verification:')
    for r in results:
        print(r)
except Exception as e:
    print('Erreur lors de la vérification automatique:', e)

