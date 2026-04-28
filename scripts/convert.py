import json
import os
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

OUTPUT_DIR = "public"

def format_posix_offset(total_seconds):
    inverted_secs = -total_seconds
    h = int(inverted_secs // 3600)
    m = int((inverted_secs % 3600) // 60)
    
    sign = "" if h >= 0 else "-"
    abs_h = abs(h)
    abs_m = abs(m)
    
    if m == 0:
        return f"{sign}{abs_h}"
    else:
        return f"{sign}{abs_h}:{abs_m:02d}"

def build_posix_rule(dt, wall_hour):
    """Convert a datetime and local wall-hour to a POSIX M.m.w.d/h rule"""
    # POSIX Day of Week: Sunday=0, Monday=1 ... Saturday=6
    dow = (dt.weekday() + 1) % 7
    month = dt.month
    
    # Calculate week of month (1 to 5)
    day_of_month = dt.day
    week = (day_of_month - 1) // 7 + 1
    
    # Check if this is the LAST week of the month
    if week >= 4:
        try:
            dt.replace(day=day_of_month + 7)
        except ValueError:
            week = 0 # 0 means "Last occurrence"
    
    return f"M{month}.{week}.{dow}/{wall_hour}"

def get_posix_string(tz_name):
    """Generate a POSIX TZ string safely by iterating in UTC"""
    try:
        tz = ZoneInfo(tz_name)
        year = datetime.now().year

        jan = datetime(year, 1, 15, tzinfo=tz)
        jul = datetime(year, 7, 15, tzinfo=tz)
        off_jan = jan.utcoffset()
        off_jul = jul.utcoffset()

        if off_jan == off_jul:
            off_str = format_posix_offset(off_jan.total_seconds())
            return f"STD{off_str}"

        if abs(off_jan) > abs(off_jul):
            std_off, dst_off = off_jul, off_jan
        else:
            std_off, dst_off = off_jan, off_jul

        std_str = format_posix_offset(std_off.total_seconds())
        dst_str = format_posix_offset(dst_off.total_seconds())

        start_rule = None
        end_rule = None
        
        # Scan using UTC to avoid Python's "Non-existent time" bug
        start_scan = datetime(year - 1, 12, 31, tzinfo=timezone.utc)
        end_scan = datetime(year + 1, 1, 2, tzinfo=timezone.utc)
        days_to_scan = (end_scan - start_scan).days

        prev_off = start_scan.astimezone(tz).utcoffset()
        
        for i in range(days_to_scan):
            day_utc = start_scan + timedelta(days=i)
            
            for hour in range(24):
                t1_utc = day_utc + timedelta(hours=hour)
                t2_utc = day_utc + timedelta(hours=hour + 1)
                
                t1_local = t1_utc.astimezone(tz)
                t2_local = t2_utc.astimezone(tz)
                
                curr_off = t1_local.utcoffset()
                
                if curr_off != prev_off:
                    # Transition detected! 
                    # Calculate the local "wall clock" hour it happened at
                    wall_hour = (t1_local.hour + 1) % 24
                    
                    # Use the local date for the rule
                    rule = build_posix_rule(t1_local, wall_hour)
                    
                    if curr_off == dst_off:
                        start_rule = rule
                    else:
                        end_rule = rule
                        
                prev_off = curr_off

        if not start_rule or not end_rule:
            off_str = format_posix_offset(std_off.total_seconds())
            return f"STD{off_str}"

        return f"STD{std_str}DST{dst_str},{start_rule},{end_rule}"

    except Exception as e:
        print(f"[ERROR] {tz_name}: {e}")
        return None

def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tz_list = sorted(available_timezones())
    
    data = {}
    print(f"Scanning {len(tz_list)} timezones for DST rules...")
    
    for tz in tz_list:
        posix = get_posix_string(tz)
        if posix:
            data[tz] = posix

    # 1. Compact JSON for ESP-32
    json_compact = json.dumps(data, separators=(',', ':'))
    with open(f"{OUTPUT_DIR}/tz.json", "w") as f:
        f.write(json_compact)

    # 2. Readable JSON for you
    json_pretty = json.dumps(data, indent=2)
    with open(f"{OUTPUT_DIR}/tzme.json", "w") as f:
        f.write(json_pretty)

    # 3. Auto Version
    hash_obj = hashlib.md5(json_compact.encode())
    auto_version = int(hash_obj.hexdigest()[:7], 16)

    with open(f"{OUTPUT_DIR}/tz_version.json", "w") as f:
        json.dump({"v": auto_version}, f)

    print(f"✅ Success! Generated {len(data)} timezones.")
    print(f"📌 Auto-Version: {auto_version}")

if __name__ == "__main__":
    generate()
