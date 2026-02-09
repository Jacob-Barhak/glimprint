from datetime import datetime
import pytz

s_date = "2026-01-22T10:00:00-05:00"
try:
    dt = datetime.fromisoformat(s_date)
    eastern = pytz.timezone('US/Eastern')
    if dt.tzinfo:
        dt_aware = dt.astimezone(eastern)
    else:
        dt_aware = eastern.localize(dt)
    
    print(f"Parsed: {dt_aware}")
    print(f"Formatted: {dt_aware.strftime('%A, %B %-d, %Y at %-I:%M %p %Z')}")
except Exception as e:
    print(f"Error: {e}")
