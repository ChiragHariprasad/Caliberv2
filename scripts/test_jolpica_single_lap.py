import urllib.request
import json

url = "http://api.jolpi.ca/ergast/f1/2023/10/laps/33.json"
req = urllib.request.Request(url, headers={"User-Agent": "PULSE-F1-Analytics/1.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read().decode())
    races = data["MRData"]["RaceTable"]["Races"]
    if races and "Laps" in races[0]:
        lap = races[0]["Laps"][0]
        print(f"Lap {lap['number']} timings count: {len(lap['Timings'])}")
        print("Sample timing:", lap["Timings"][0])

