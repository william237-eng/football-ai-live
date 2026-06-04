from modules.top_victories.victory_storage import get_daily_stats, get_weekly_stats, get_prediction_history

print('Daily:')
print(get_daily_stats())
print('\nWeekly:')
print(get_weekly_stats())
print('\nRecent history:')
for p in get_prediction_history(5):
    print(p)

