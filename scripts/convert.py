import json
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

OUTPUT_DIR = "public"
YEAR = datetime.now().year

def get_dst_transitions(tz_name):
    """Find the next DST start and end transitions for a timezone."""
    tz = ZoneInfo(tz_name)
    
    # Check standard and DST offsets by looking at Jan and July
    jan = datetime(YEAR, 1, 1, tzinfo=tz)
    jul = datetime(YEAR, 7, 1, tzinfo=tz)
    
    std_offset = jan.utcoffset()
    dst_offset = jul.utcoffset()
    
    # If they are the same, there is no DST
    if std_offset == dst_offset:
        return None, None, std_offset, dst_offset

    # Determine which is STD and which is DST based on offset magnitude
    # (DST is always further from zero than Standard, e.g., -5 vs -4, or +1 vs +2)
    if abs(std_offset) > abs(dst_offset):
        actual_std_offset, actual_dst_offset = dst_offset, std_offset
        is_dst_in_jan = True  # Southern hemisphere
    else:
        actual_std_offset, actual_dst_offset = std_offset, dst_offset
        is_dst_in_jan = False

    # Scan day-by-day to find the exact transition dates
    start_rule = None
    end_rule = None

    # Check a 14-month window to catch end-of-year transitions
    start_date = datetime(YEAR - 1, 12, 1)
    
    for i in range(450): # ~15 months
        day = start_date + timedelta(days=i)
        day_tz = day.replace(tzinfo=tz)
        current_offset = day_tz.utcoffset()
        next_day_tz = (day + timedelta(days=1)).replace(tzinfo=tz)
        next_offset = next_day_tz.utcoffset()

        if current_offset != next_offset:
            # A transition happened overnight. Find the exact hour.
            for hour in range(24):
                check_time = day.replace(hour=hour, minute=0, second=0, tzinfo=tz)
                next_hour = check_time + timedelta(hours=1)
                
                if check_time.utcoffset() != next_hour.utcoffset():
                    transition_dt = check_time
                    rule = build_esp32_rule(transition_dt)
                    
                    # Figure out if this is DST starting or ending
                    if next_hour.utcoffset() == actual_dst_offset:
                        start_rule = rule # DST is starting
                    else:
                        end_rule = rule   # DST is ending
                    break

        if start_rule and end_rule:
            break

    return start_rule, end_rule, actual_std_offset, actual_dst_offset

def build_esp32_rule(dt):
    """Convert a datetime transition to ESP32 TimeChangeRule numbers."""
    # POSIX/ESP32 DOW: Sun=0, Mon=1 ... Sat=6
    dow = dt.weekday() + 1 if dt.weekday() < 6 else 0 
    
    # Calculate week of month
    day_of_month = dt.day
    week = (day_of_month - 1) // 7 + 1
    
    # Check if this is the LAST week of the month
    if week >= 4:
        next_week_same_dow = day_of_month + 7
        try:
            dt.replace(day=next_week_same_dow)
        except ValueError:
            week = 0 # 0 means "Last week" in ESP32 Timezone library

    return {
        "month": dt.month,
        "week": week,
        "dow": dow,
        "hour": dt.hour
    }

def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Get a list of common timezones (or use timedatectl like you did before)
    # Hardcoding a reasonable list saves generation time, but here is how to get all:
    import subprocess
    tz_list = subprocess.run(
        ["timedatectl", "list-timezones"], 
        capture_output=True, text=True
    ).stdout.splitlines()

    data = {}

    for tz in tz_list:
        try:
            start_rule, end_rule, std_off, dst_off = get_dst_transitions(tz)
            
            data[tz] = {
                "stdOffset": int(std_off.total_seconds() / 60),
                "dstOffset": int(dst_off.total_seconds() / 60),
                "dstStart": start_rule,
                "dstEnd": end_rule
            }
            print(f"[OK] {tz}")
        except Exception as e:
            print(f"[FAIL] {tz}: {e}")

    with open(f"{OUTPUT_DIR}/tz.json", "w") as f:
        json.dump(data, f, indent=2)

    print(f"\nGenerated rules for {len(data)} timezones.")

if __name__ == "__main__":
    generate()
