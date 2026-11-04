import fastf1
import os

cache_dir = "data/fastf1_cache"
os.makedirs(cache_dir, exist_ok=True)
fastf1.Cache.enable_cache(cache_dir)

candidates = [
    (2023, "Monaco"),
    (2023, "British Grand Prix"),
    (2023, "Dutch Grand Prix"),
]

for yr, gp in candidates:
    print(f"\n==========================================")
    print(f"Evaluating {yr} {gp} (Race)...")
    try:
        session = fastf1.get_session(yr, gp, "R")
        session.load(telemetry=True, weather=True, messages=True)
        print(f"  [+] Session Name: {session.event['EventName']}")
        print(f"  [+] Date: {session.date}")
        print(f"  [+] Drivers count: {len(session.drivers)}")
        print(f"  [+] Drivers: {session.drivers}")
        print(f"  [+] Laps count: {len(session.laps)}")
        rc_count = len(session.race_control_messages) if hasattr(session, "race_control_messages") and session.race_control_messages is not None else 0
        print(f"  [+] Race Control messages count: {rc_count}")
        weather_count = len(session.weather_data) if hasattr(session, "weather_data") and session.weather_data is not None else 0
        print(f"  [+] Weather records count: {weather_count}")
        
        # Check telemetry for car 1 (Verstappen) or leader
        leader_laps = session.laps.pick_drivers("1")
        if not leader_laps.empty:
            fastest = leader_laps.pick_fastest()
            if fastest is not None:
                car_data = fastest.get_car_data()
                print(f"  [+] Car #1 fastest lap telemetry points: {len(car_data)}")
                print(f"  [+] Telemetry channels: {list(car_data.columns)}")
                pos_data = fastest.get_pos_data()
                print(f"  [+] Car #1 fastest lap pos points: {len(pos_data)}")
                print(f"  [+] Pos channels: {list(pos_data.columns)}")
    except Exception as e:
        print(f"  [-] Failed: {e}")

