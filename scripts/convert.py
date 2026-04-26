import json
from datetime import datetime

zones = {
    "UTC": "UTC0",
    "Asia/Amman": "AST-3",
    "Europe/London": "GMT0BST,M3.5.0/1,M10.5.0",
    "America/New_York": "EST5EDT,M3.2.0/2,M11.1.0/2"
}

version = datetime.utcnow().strftime("%Y.%m.%d")

data = {
    "version": version,
    "zones": zones
}

with open("public/tz.json", "w") as f:
    json.dump(data, f, indent=2)

with open("public/tz_version.json", "w") as f:
    json.dump({"version": version}, f)

print("TZ files generated")

