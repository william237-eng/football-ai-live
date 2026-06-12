"""Smoke test for registry compute_real_stats functions.

Run this script to validate that each registry's `compute_real_stats(days)`
returns a dict with expected keys: at least one of 'won'/'wins' and 'roi'/'winrate'.
Exit code 0 on success, 2 on failure.
"""
import importlib
import sys

modules = [
    'modules.top_under25_live.prediction_registry',
    'modules.top_over25_live.prediction_registry',
    'modules.daily_predictions.prediction_registry',
    'modules.daily_predictions.prediction_registry_red',
    'modules.daily_predictions.prediction_registry_yellow_3_5',
    'modules.world_cup.prediction_registry_worldcup',
]

errors = []
for mod in modules:
    try:
        m = importlib.import_module(mod)
        func = getattr(m, 'compute_real_stats', None)
        if not callable(func):
            errors.append(f"{mod}: missing compute_real_stats")
            continue
        stats = func(days=30)
        if not isinstance(stats, dict):
            errors.append(f"{mod}: compute_real_stats did not return a dict")
            continue
        if not (stats.get('won') is not None or stats.get('wins') is not None):
            errors.append(f"{mod}: missing 'won'/'wins' key in stats")
        if 'roi' not in stats and 'winrate' not in stats and 'winrate_pct' not in stats:
            errors.append(f"{mod}: missing 'roi'/'winrate' key in stats")
    except Exception as e:
        errors.append(f"{mod}: import or execution error: {e}")

if errors:
    print('SMOKE TEST FAILED')
    for e in errors:
        print('-', e)
    sys.exit(2)

print('SMOKE TEST PASSED')
sys.exit(0)
