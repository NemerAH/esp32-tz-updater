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
    dow = (dt.weekday() + 1) % 7
    month = dt.month
    day_of_month = dt.day
    week = (day_of_month - 1) // 7 + 1
    if week >= 4:
        try:
            dt.replace(day=day_of_month + 7)
        except ValueError:
            week = 0  # last occurrence
    return f"M{month}.{week}.{dow}/{wall_hour}"

def get_std_abbr(tz_name):
    """Return a sane abbreviation (e.g., 'EET' for Europe/Helsinki)"""
    try:
        now = datetime.now()
        abbr = now.astimezone(ZoneInfo(tz_name)).tzname()
        if abbr and not any(c in abbr for c in '+-\d'):
            return abbr
    except:
        pass
    # Fallback: generate from tz_name
    parts = tz_name.split('/')
    if len(parts) > 1:
        return parts[-1][:3].upper()
    return tz_name[:3].upper()

def get_posix_string(tz_name):
    try:
        tz = ZoneInfo(tz_name)
        year = datetime.now().year

        jan = datetime(year, 1, 15, tzinfo=tz)
        jul = datetime(year, 7, 15, tzinfo=tz)
        off_jan = jan.utcoffset()
        off_jul = jul.utcoffset()

        if off_jan == off_jul:
            off_str = format_posix_offset(off_jan.total_seconds())
            return f"{get_std_abbr(tz_name)}{off_str}"

        # Determine std and dst offsets (std is the smaller absolute offset)
        if abs(off_jan) > abs(off_jul):
            std_off, dst_off = off_jul, off_jan
            std_abbr = get_std_abbr(tz_name)
            dst_abbr = get_std_abbr(tz_name) + "ST"  # e.g. EEST
        else:
            std_off, dst_off = off_jan, off_jul
            std_abbr = get_std_abbr(tz_name)
            dst_abbr = get_std_abbr(tz_name) + "ST"

        std_str = format_posix_offset(std_off.total_seconds())
        dst_str = format_posix_offset(dst_off.total_seconds())

        # Find transition times
        start_rule = end_rule = None
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
                    wall_hour = (t1_local.hour + 1) % 24
                    rule = build_posix_rule(t1_local, wall_hour)
                    if curr_off == dst_off:
                        start_rule = rule
                    else:
                        end_rule = rule
                prev_off = curr_off

        if not start_rule or not end_rule:
            # fallback to fixed offset
            off_str = format_posix_offset(std_off.total_seconds())
            return f"{std_abbr}{off_str}"

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

    json_compact = json.dumps(data, separators=(',', ':'))
    with open(f"{OUTPUT_DIR}/tz.json", "w") as f:
        f.write(json_compact)

    json_pretty = json.dumps(data, indent=2)
    with open(f"{OUTPUT_DIR}/tzme.json", "w") as f:
        f.write(json_pretty)

    hash_obj = hashlib.md5(json_compact.encode())
    auto_version = int(hash_obj.hexdigest()[:7], 16)
    with open(f"{OUTPUT_DIR}/tz_version.json", "w") as f:
        json.dump({"v": auto_version}, f)

    print(f"✅ Generated {len(data)} timezones. Version: {auto_version}")

if __name__ == "__main__":
    generate()
