import urllib.request
import json

url = "http://api.jolpi.ca/ergast/f1/2023/10/laps.json?limit=1000"
req = urllib.request.Request(url, headers={"User-Agent": "PULSE-F1-Analytics/1.0"})
with urllib.request.urlopen(req, timeout=15) as resp:
    data = json.loads(resp.read().decode())
    races = data["MRData"]["RaceTable"]["Races"]
    if races and "Laps" in races[0]:
        laps = races[0]["Laps"]
        print(f"Laps count returned with limit=1000: {len(laps)} laps!")
        total_timings = sum(len(l["Timings"]) for l in laps)
        print(f"Total timings returned in single request: {total_timings} / 970!")

