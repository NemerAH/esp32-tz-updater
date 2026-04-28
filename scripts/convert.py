import json
import os
import hashlib
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, available_timezones

OUTPUT_DIR = "public"

def format_posix_offset(total_seconds):
    """
    POSIX offsets are inverted! 
    e.g., UTC-5 (New York) is written as "5". UTC+5:30 (India) is written as "-5:30".
    """
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

def build_posix_rule(dt):
    """Convert a datetime transition to a POSIX M.m.w.d/h rule"""
    # POSIX Day of Week: Sunday=0, Monday=1 ... Saturday=6
    dow = (dt.weekday() + 1) % 7
    month = dt.month
    hour = dt.hour
    
    # Calculate week of month (1 to 5)
    day_of_month = dt.day
    week = (day_of_month - 1) // 7 + 1
    
    # Check if this is the LAST week of the month
    # If adding 7 days goes past the month, it's the last week (represented as 0 in POSIX)
    if week >= 4:
        try:
            dt.replace(day=day_of_month + 7)
        except ValueError:
            week = 0 # 0 means "Last occurrence of this weekday in the month"
    
    return f"M{month}.{week}.{dow}/{hour}"

def get_posix_string(tz_name):
    """Generate a POSIX TZ string for a given IANA timezone using pure Python"""
    try:
        tz = ZoneInfo(tz_name)
        year = datetime.now().year

        # Check opposite seasons to find Standard vs DST offsets
        jan = datetime(year, 1, 15, tzinfo=tz)
        jul = datetime(year, 7, 15, tzinfo=tz)
        off_jan = jan.utcoffset()
        off_jul = jul.utcoffset()

        # If they are the same, there is no DST
        if off_jan == off_jul:
            off_str = format_posix_offset(off_jan.total_seconds())
            return f"STD{off_str}"

        # DST offset is always further from zero than Standard (e.g., -4 is further than -5)
        if abs(off_jan) > abs(off_jul):
            std_off, dst_off = off_jul, off_jan
        else:
            std_off, dst_off = off_jan, off_jul

        std_str = format_posix_offset(std_off.total_seconds())
        dst_str = format_posix_offset(dst_off.total_seconds())

        # Scan the current year to find the exact transition hours
        start_rule = None
        end_rule = None
        
        start_scan = datetime(year - 1, 12, 31, tzinfo=tz)
        end_scan = datetime(year + 1, 1, 2, tzinfo=tz)
        days_to_scan = (end_scan - start_scan).days

        prev_off = start_scan.utcoffset()
        for i in range(days_to_scan):
            day = start_scan + timedelta(days=i)
            curr_off = day.utcoffset()
            
            if curr_off != prev_off:
                # A transition happened overnight! Find the exact hour.
                for hour in range(24):
                    t1 = day.replace(hour=hour, minute=0, second=0, tzinfo=tz)
                    t2 = t1 + timedelta(hours=1)
                    
                    if t1.utcoffset() != t2.utcoffset():
                        rule = build_posix_rule(t1)
                        
                        # If the new time (t2) is DST, this is the START rule.
                        # If the new time (t2) is Standard, this is the END rule.
                        # This automatically handles Northern & Southern hemispheres!
                        if t2.utcoffset() == dst_off:
                            start_rule = rule
                        else:
                            end_rule = rule
                        break
            prev_off = curr_off

        if not start_rule or not end_rule:
            # Fallback for weird edge cases (e.g., permanent DST changes mid-year)
            off_str = format_posix_offset(std_off.total_seconds())
            return f"STD{off_str}"

        # Final POSIX String format
        return f"STD{std_str}DST{dst_str},{start_rule},{end_rule}"

    except Exception as e:
        print(f"[ERROR calculating rules] {tz_name}: {e}")
        return None

def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Get all IANA timezones natively (No external tools needed!)
    tz_list = sorted(available_timezones())
    
    data = {}
    
    print(f"Generating rules for {len(tz_list)} timezones...")
    for tz in tz_list:
        posix = get_posix_string(tz)
        if posix:
            data[tz] = posix

    # 1. Generate the compact JSON (for ESP-32 - tiny and fast)
    json_compact = json.dumps(data, separators=(',', ':'))
    with open(f"{OUTPUT_DIR}/tz.json", "w") as f:
        f.write(json_compact)

    # 2. Generate the readable JSON (for you to check on GitHub)
    json_pretty = json.dumps(data, indent=2)
    with open(f"{OUTPUT_DIR}/tzme.json", "w") as f:
        f.write(json_pretty)

    # 3. AUTOMATIC VERSION GENERATION
    hash_obj = hashlib.md5(json_compact.encode())
    auto_version = int(hash_obj.hexdigest()[:7], 16)

    # 4. Save the automatic version
    with open(f"{OUTPUT_DIR}/tz_version.json", "w") as f:
        json.dump({"v": auto_version}, f)

    print(f"✅ Success! Generated {len(data)} timezones.")
    print(f"📌 Auto-Version: {auto_version}")

if __name__ == "__main__":
    generate()
