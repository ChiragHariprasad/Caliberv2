import urllib.request
import json
import time

def post(url, data_dict):
    req = urllib.request.Request(
        url,
        data=json.dumps(data_dict).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get(url):
    with urllib.request.urlopen(url) as resp:
        return json.loads(resp.read())

print("Setting speed to 5.0...")
post("http://127.0.0.1:8000/api/replay/speed", {"speed": 5.0})
print("Starting replay...")
post("http://127.0.0.1:8000/api/replay/start", {})

for i in range(5):
    time.sleep(1.0)
    snap = get("http://127.0.0.1:8000/api/snapshot")
    rep = get("http://127.0.0.1:8000/api/replay/status")
    print(f"Sec {i+1}: idx={rep.get('currentIndex')}, findings={len(snap.get('findings', []))}, assessments={len(snap.get('assessments', []))}")

post("http://127.0.0.1:8000/api/replay/pause", {})

