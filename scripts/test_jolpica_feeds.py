import urllib.request
import json

base = "http://api.jolpi.ca/ergast/f1/2023/10"
for endpoint, label in [("pitstops.json?limit=100", "Pit Stops"), ("laps.json?limit=100", "Laps (first 100)")]:
    url = f"{base}/{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "PULSE-F1-Analytics/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            races = data["MRData"]["RaceTable"]["Races"]
            if races:
                race = races[0]
                if "PitStops" in race:
                    stops = race["PitStops"]
                    print(f"[+] Total {label}: {len(stops)} stops found.")
                    for s in stops[:3]:
                        print(f"    Driver #{s['driverId']} - Stop {s['stop']} on Lap {s['lap']} - Duration: {s['duration']}s at {s['time']}")
                elif "Laps" in race:
                    laps = race["Laps"]
                    print(f"[+] Total {label}: {len(laps)} lap entries found.")
                    for l in laps[:2]:
                        print(f"    Lap {l['number']} has {len(l['Timings'])} driver timings.")
    except Exception as e:
        print(f"[-] {label} failed: {e}")

