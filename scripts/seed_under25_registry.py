from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.top_under25_live.prediction_registry import register_prediction, get_all_predictions

samples = [
    {"fixture_id": 2001000 + i,
     "home_name": f"Home{i}",
     "away_name": f"Away{i}",
     "league_name": "Demo League",
     "league_country": "Test",
     "start_time": "12:00",
     "start_date_display": "04/06/2026",
     "under25_prob": 0.75 - i*0.05,
     "under25_pct": int((0.75 - i*0.05)*100),
     "conf_label": "Modérée",
     "under_score": 60 + i,
     "match_type": "future"
    } for i in range(5)
]

for s in samples:
    ok = register_prediction(s)
    print(f"Registered {s['fixture_id']}: {ok}")

print('Total now in registry:', len(get_all_predictions()))

