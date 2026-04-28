import json
import os
import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, available_timezones

OUTPUT_DIR = "public"

# Common abbreviation mapping (standard + DST)
ABBR_MAP = {
    "GMT": ("GMT", "BST"),
    "CET": ("CET", "CEST"),
    "EET": ("EET", "EEST"),
    "WET": ("WET", "WEST"),
    "EST": ("EST", "EDT"),
    "CST": ("CST", "CDT"),
    "MST": ("MST", "MDT"),
    "PST": ("PST", "PDT"),
    "IST": ("IST", "IDT"),
    "JST": ("JST", None),
    "KST": ("KST", None),
    "MSK": ("MSK", None),
    # Add more as needed
}

def format_posix_offset(total_seconds):
    """Convert offset seconds to POSIX ±HH[:MM]"""
    inverted_secs = -total_seconds
    h = int(inverted_secs // 3600)
    m = int((inverted_secs % 3600) // 60)
    sign = "" if h >= 0 else "-"
    abs_h, abs_m = abs(h), abs(m)
    if m == 0:
        return f"{sign}{abs_h}"
    else:
        return f"{sign}{abs_h}:{abs_m:02d}"

def get_abbreviations(tz_name):
    """Return (std_abbr, dst_abbr) using known map or fallback"""
    # Extract base name for lookup
    base = tz_name.split('/')[-1].replace('_', ' ')
    # Try known map
    for key, (std, dst) in ABBR_MAP.items():
        if key in base or key in tz_name:
            return std, dst
    # Fallback: use first 3 letters of last part, uppercase
    fallback = tz_name.split('/')[-1][:3].upper()
    return fallback, (fallback + "ST")

def build_posix_rule(dt, wall_hour):
    """Generate Mmonth.week.day/hour rule (week 5 = last occurrence)"""
    dow = (dt.weekday() + 1) % 7   # Sunday=0, Monday=1 … Saturday=6
    month = dt.month
    day = dt.day
    week = (day - 1) // 7 + 1
    # Check if this is the last week of the month
    try:
        dt.replace(day=day + 7)
    except ValueError:
        week = 5   # POSIX uses 5 for last occurrence
    return f"M{month}.{week}.{dow}/{wall_hour}"

def get_posix_string(tz_name):
    try:
        tz = ZoneInfo(tz_name)
        year = datetime.now().year

        # Sample two dates – January and July (northern hemisphere)
        jan = datetime(year, 1, 15, tzinfo=tz)
        jul = datetime(year, 7, 15, tzinfo=tz)
        off_jan = jan.utcoffset()
        off_jul = jul.utcoffset()

        std_abbr, dst_abbr = get_abbreviations(tz_name)

        # No DST
        if off_jan == off_jul:
            off_str = format_posix_offset(off_jan.total_seconds())
            return f"{std_abbr}{off_str}"

        # Determine which is standard (smaller absolute offset) and which is DST
        if abs(off_jan.total_seconds()) < abs(off_jul.total_seconds()):
            std_off, dst_off = off_jan, off_jul
        else:
            std_off, dst_off = off_jul, off_jan

        std_str = format_posix_offset(std_off.total_seconds())
        dst_str = format_posix_offset(dst_off.total_seconds())

        # Scan for transitions
        start_rule = end_rule = None
        # Scan over two years to catch all transitions
        start_scan = datetime(year - 1, 12, 31, tzinfo=timezone.utc)
        end_scan = datetime(year + 1, 1, 2, tzinfo=timezone.utc)
        days = (end_scan - start_scan).days

        prev_off = start_scan.astimezone(tz).utcoffset()
        for i in range(days):
            day_utc = start_scan + timedelta(days=i)
            for hour in range(24):
                t1_utc = day_utc + timedelta(hours=hour)
                t2_utc = day_utc + timedelta(hours=hour+1)
                t1_local = t1_utc.astimezone(tz)
                t2_local = t2_utc.astimezone(tz)
                curr_off = t1_local.utcoffset()
                if curr_off != prev_off:
                    # Transition detected
                    # The transition happens at the "wall hour" of t2_local (the new time)
                    wall_hour = t2_local.hour
                    rule = build_posix_rule(t2_local, wall_hour)
                    if curr_off == dst_off:
                        start_rule = rule   # switch from std to dst
                    else:
                        end_rule = rule     # switch from dst to std
                prev_off = curr_off

        if not start_rule or not end_rule:
            # Fallback to fixed offset
            off_str = format_posix_offset(std_off.total_seconds())
            return f"{std_abbr}{off_str}"

        # Standard POSIX format: STDstd_offsetDSTdst_offset,start_rule,end_rule
        return f"{std_abbr}{std_str}{dst_abbr}{dst_str},{start_rule},{end_rule}"

    except Exception as e:
        print(f"[ERROR] {tz_name}: {e}")
        return None

def generate():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tz_list = sorted(available_timezones())
    data = {}
    print(f"Scanning {len(tz_list)} timezones...")
    for tz in tz_list:
        posix = get_posix_string(tz)
        if posix:
            data[tz] = posix

    # Compact JSON for ESP32
    json_compact = json.dumps(data, separators=(',', ':'))
    with open(f"{OUTPUT_DIR}/tz.json", "w") as f:
        f.write(json_compact)

    # Pretty JSON for human review
    json_pretty = json.dumps(data, indent=2)
    with open(f"{OUTPUT_DIR}/tzme.json", "w") as f:
        f.write(json_pretty)

    # Version hash based on content
    hash_obj = hashlib.md5(json_compact.encode())
    auto_version = int(hash_obj.hexdigest()[:7], 16)
    with open(f"{OUTPUT_DIR}/tz_version.json", "w") as f:
        json.dump({"v": auto_version}, f)

    print(f"✅ Generated {len(data)} timezones. Version: {auto_version}")

if __name__ == "__main__":
    generate()
