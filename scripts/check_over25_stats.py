import sys
from pathlib import Path
# ensure project root is on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules.top_over25_live.prediction_registry import get_all_predictions
from datetime import datetime, timezone, timedelta

all_preds = get_all_predictions()
now = datetime.now(timezone.utc)
start_today = now - timedelta(days=1)
start_week = now - timedelta(days=7)

preds_today = [p for p in all_preds if p.get('timestamp_prediction') and datetime.fromisoformat(p['timestamp_prediction']) >= start_today]
preds_week = [p for p in all_preds if p.get('timestamp_prediction') and datetime.fromisoformat(p['timestamp_prediction']) >= start_week]

print(f"Total predictions: {len(all_preds)}")
print(f"Today: {len(preds_today)}")
print(f"7 days: {len(preds_week)}")
if preds_today:
    for p in preds_today:
        print('-', p.get('timestamp_prediction'), p.get('home_name') or p.get('home_team'), 'vs', p.get('away_name') or p.get('away_team'), p.get('status'), p.get('result'))

