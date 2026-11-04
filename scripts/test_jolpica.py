import urllib.request
import json

url = "http://api.jolpi.ca/ergast/f1/2023/10/results.json"
print("Fetching Jolpica-F1 2023 Round 10 (Silverstone) results...")
req = urllib.request.Request(url, headers={"User-Agent": "PULSE-F1-Analytics/1.0"})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
        race = data["MRData"]["RaceTable"]["Races"][0]
        print("Race:", race["raceName"], race["date"])
        results = race["Results"]
        print("Total classified drivers:", len(results))
        for r in results[:5]:
            d = r["Driver"]
            pos = r["position"]
            num = r["number"]
            name = f"{d['givenName']} {d['familyName']}"
            team = r["Constructor"]["name"]
            status = r["status"]
            print(f"P{pos}: #{num} {name} ({team}) - Status: {status}")
except Exception as e:
    print("Failed:", e)

