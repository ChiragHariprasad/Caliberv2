import fastf1

print("FastF1 version:", fastf1.__version__)
# Check what session objects have
try:
    session = fastf1.get_session(2023, "Silverstone", "R")
    # Try loading only laps first
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    print("Loaded laps successfully! Total laps:", len(session.laps))
    # Pick a lap
    lap = session.laps.pick_drivers("1").pick_fastest()
    print("Fastest lap for #1:", lap["LapTime"])
    # Can we get car data for this lap?
    try:
        car_data = lap.get_car_data()
        print("Car data points:", len(car_data))
    except Exception as e:
        print("get_car_data failed:", e)
except Exception as e:
    print("Session load failed:", e)

