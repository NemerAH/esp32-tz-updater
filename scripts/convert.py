"""
Timezone Database Converter
Converts IANA timezone data into JSON format for ESP32 consumption
"""

import json
import os
from datetime import datetime, timezone
from zoneinfo import available_timezones

def generate_tz_data():
    """Generate timezone database from Python's built-in IANA data"""
    
    tz_data = {}
    
    # Get all available timezones from Python's zoneinfo
    all_timezones = sorted(available_timezones())
    
    for tz_name in all_timezones:
        # Skip POSIX-style timezone names (starting with + or -)
        if tz_name.startswith(('+', '-')):
            continue
        
        tz_data[tz_name] = {
            "name": tz_name,
            # Add any additional fields your ESP32 code needs
        }
    
    return tz_data


def main():
    # Ensure public directory exists
    os.makedirs("public", exist_ok=True)
    
    # Generate timezone data
    tz_data = generate_tz_data()
    
    # Write tz.json
    with open("public/tz.json", "w", encoding="utf-8") as f:
        json.dump(tz_data, f, indent=2, ensure_ascii=False)
    
    print(f"Generated tz.json with {len(tz_data)} timezones")
    
    # Write version file
    version_info = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "timezone_count": len(tz_data),
        "source": "IANA timezone database via Python zoneinfo"
    }
    
    with open("public/tz_version.json", "w", encoding="utf-8") as f:
        json.dump(version_info, f, indent=2)
    
    print(f"Generated tz_version.json")
    print(f"Version: {version_info['generated_at']}")


if __name__ == "__main__":
    main()
