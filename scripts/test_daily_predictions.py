import json
import sys
from pathlib import Path

# Assurer que le répertoire racine du projet est dans sys.path (utile si exécuté depuis PowerShell)
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.daily_predictions.daily_predictions_engine import fetch_daily_predictions


class MockAPI:
    """Mock minimal pour tester fetch_daily_predictions sans appeler l'API réelle."""
    def get_fixtures_by_date(self, date):
        # Retourne un tuple similaire à l'API réelle: (raw, meta)
        return ({'response': []}, None)

    def get_team_recent_fixtures(self, team_id, count=6):
        return {'response': []}

    def get_team_fixtures(self, team_id=None, season=None, last=6):
        return {'response': []}


def main():
    api = MockAPI()
    print('Calling fetch_daily_predictions...')
    try:
        res = fetch_daily_predictions(api)
    except Exception as e:
        print('fetch_daily_predictions raised:', repr(e))
        sys.exit(2)

    print('Result keys:', list(res.keys()))
    for k, v in res.items():
        print(f"- {k}: {len(v)} items")

    # print a compact JSON for inspection
    try:
        print(json.dumps(res, indent=2, default=str))
    except Exception:
        print('Could not JSON-dump results (contains non-serializable objects)')


if __name__ == '__main__':
    main()

