import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.top_over25_live.prediction_registry import get_pending_predictions, get_all_predictions
from modules.top_over25_live.over25_monitor import validate_pending

class MockAPI:
    def __init__(self):
        pass
    def get_fixture_detail(self, fixture_id):
        # Build a fake API response with FT and alternating totals
        # For even ids -> total 3 (VALIDATED), odd ids -> total 2 (FAILED)
        hid = fixture_id
        if isinstance(fixture_id, str) and fixture_id.isdigit():
            fid = int(fixture_id)
        else:
            fid = fixture_id
        if fid % 2 == 0:
            home, away = 2, 1
        else:
            home, away = 1, 1
        resp = {
            "response": [
                {
                    "fixture": {"id": fid, "status": {"short": "FT"}},
                    "goals": {"home": home, "away": away}
                }
            ]
        }
        return resp

if __name__ == '__main__':
    pending = get_pending_predictions()
    print(f"Pending before: {len(pending)}")
    api = MockAPI()
    updated = validate_pending(api)
    print(f"Updated count: {len(updated)}")
    for u in updated[:10]:
        print(u)
    pending_after = get_pending_predictions()
    print(f"Pending after: {len(pending_after)}")
    all_preds = get_all_predictions()
    print(f"Total predictions now: {len(all_preds)}")

