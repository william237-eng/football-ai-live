import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.top_under25_live.prediction_registry import get_all_predictions, get_pending_predictions
from modules.top_under25_live.under25_monitor import validate_pending

# Ensure there is at least one pending in registry for test
allp = get_all_predictions()
print('Before registry count:', len(allp))
pend = get_pending_predictions()
print('Pending before:', len(pend))

class MockAPI:
    def get_fixture_detail(self, fixture_id):
        # make FT with total even => VALIDATED if <=2 else FAILED
        fid = int(fixture_id)
        # produce alternating totals: even id -> total 2, odd id -> total 3
        if fid % 2 == 0:
            home, away = 1, 1
        else:
            home, away = 2, 1
        return {"response": [{"fixture": {"id": fid, "status": {"short": "FT"}}, "goals": {"home": home, "away": away}}]}

if __name__ == '__main__':
    api = MockAPI()
    updated = validate_pending(api)
    print('Updated:', len(updated))
    for u in updated[:5]:
        print(u)
    print('Pending after:', len(get_pending_predictions()))
    print('Total now:', len(get_all_predictions()))

