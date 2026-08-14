import time
import random
import requests

SERVER_URL = "http://127.0.0.1:8000/api/v1/telemetry"
DEVICE_ID = "SUPERBREW_ECO_01"

def run_simulator():
    print("==================================================")
    print("   EcoSense Telemetry & Thermal Simulator        ")
    print("==================================================")
    print("Streaming live telemetry to http://127.0.0.1:8000")
    print("Inactivity (>10s) will automatically trigger ECO MODE!\n")

    current_temp = 92.0
    last_brew = time.time()

    while True:
        now = time.time()
        brew_active = False

        # Simulate an occasional brew order (12% chance per tick)
        if random.random() < 0.12:
            brew_active = True
            last_brew = now
            print("\n[BREW EVENT] Dispensing Beverage! Returning heater to 92°C.")

        idle_seconds = now - last_brew

        if idle_seconds > 10.0:
            # ECO MODE STATE: Low power draw, target temp drops to ~65°C
            if current_temp > 65.0:
                current_temp -= 0.9  # Cooling down
            power_watts = round(random.uniform(500.0, 650.0), 1)
        else:
            # ACTIVE STATE: Full heater power, target temp ~92°C
            if current_temp < 92.0:
                current_temp += 1.5  # Rapid re-heating
            power_watts = round(random.uniform(2100.0, 2300.0), 1)

        current_temp = round(max(60.0, min(96.0, current_temp)), 1)

        payload = {
            "device_id": DEVICE_ID,
            "power_watts": power_watts,
            "temp_c": current_temp,
            "brew_active": brew_active
        }

        try:
            res = requests.post(SERVER_URL, json=payload, timeout=2)
            mode = res.json().get("mode", "UNKNOWN")
            print(f"[SENT] Mode: {mode:<10} | Power: {power_watts}W | Temp: {current_temp}°C")
        except Exception as e:
            print(f"[ERROR] Could not connect to backend server: {e}")

        time.sleep(1)

if __name__ == "__main__":
    run_simulator()