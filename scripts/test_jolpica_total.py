import urllib.request
import json
import time

url = "http://api.jolpi.ca/ergast/f1/2023/10/laps.json?limit=100&offset=0"
req = urllib.request.Request(url, headers={"User-Agent": "PULSE-F1-Analytics/1.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())
    total = int(data["MRData"]["total"])
    print(f"Total lap timing records in Jolpica-F1 for 2023 Round 10: {total}")
    races = data["MRData"]["RaceTable"]["Races"]
    if races:
        laps = races[0]["Laps"]
        print(f"First page returned {len(laps)} laps.")

