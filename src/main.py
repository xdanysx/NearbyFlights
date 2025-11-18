# -*- coding: utf-8 -*-
import os
import time
import math
import requests
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "data" / "config.txt"
API_PATH = BASE_DIR / "data" / "opensky_api.txt"

# OpenSky Login (optional)
OS_USER = os.getenv("OPEN_SKY_USER", "").strip()
OS_PASS = os.getenv("OPEN_SKY_PASS", "").strip()

OS_STATES_URL = "https://opensky-network.org/api/states/all"
OS_FLIGHTS_AC = "https://opensky-network.org/api/flights/aircraft"
# ================================================================


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "data" / "config.txt"
API_PATH = BASE_DIR / "data" / "opensky_api.txt"

def load_kv_file(path: Path):
    data = {}
    if not path.exists():
        raise RuntimeError(f"Konfigurationsdatei fehlt: {path}")
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            data[k.strip()] = v.strip()
    return data

config = load_kv_file(CONFIG_PATH)
CENTER_LAT  = float(config.get("CENTER_LAT", 60))  # Standard-Koordinate (du kannst diese beim Start ändern) 
CENTER_LON  = float(config.get("CENTER_LON", 20))
RADIUS_KM   = float(config.get("RADIUS_KM", 40)) # Default-Radius
MAX_RESULTS = int(config.get("MAX_RESULTS", 20)) # Max Ergebnisse für Listen-Modus

api_cfg = load_kv_file(API_PATH)
OS_STATES_URL = api_cfg.get("STATES_URL")
OS_FLIGHTS_AC = api_cfg.get("FLIGHTS_AC_URL")



def bbox_from_center(lat, lon, radius_km):
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.0001, math.cos(math.radians(lat))))
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2 * R * math.asin(math.sqrt(a))


def mps_to_knots(mps):
    return mps * 1.9438444924406


def mps_to_kmh(mps):
    return mps * 3.6


def meters_to_feet(m):
    return m * 3.280839895


def fetch_states_nearby(center_lat, center_lon, radius_km):
    lamin, lamax, lomin, lomax = bbox_from_center(center_lat, center_lon, radius_km)
    params = {"lamin": lamin, "lamax": lamax, "lomin": lomin, "lomax": lomax}
    try:
        r = requests.get(OS_STATES_URL, params=params, timeout=15, headers={"User-Agent": "NearbyFlights/1.0"})
        r.raise_for_status()
    except requests.RequestException as e:
        print("Fehler beim Abruf von OpenSky:", e)
        return []
    data = r.json() if r.text else {}
    states = data.get("states") or []
    out = []
    for s in states:
        icao24   = s[0]
        callsign = (s[1] or "").strip()
        lon      = s[5]
        lat      = s[6]
        alt_m    = s[7]
        on_gnd   = s[8]
        vel_mps  = s[9]
        track    = s[10]
        if lat is None or lon is None:
            continue
        dist_km = haversine_km(center_lat, center_lon, lat, lon)
        out.append({
            "icao24": icao24,
            "callsign": callsign,
            "lat": lat,
            "lon": lon,
            "alt_m": alt_m,
            "alt_ft": meters_to_feet(alt_m) if isinstance(alt_m, (int, float)) else None,
            "vel_mps": vel_mps,
            "vel_kmh": mps_to_kmh(vel_mps) if isinstance(vel_mps, (int, float)) else None,
            "vel_kt": mps_to_knots(vel_mps) if isinstance(vel_mps, (int, float)) else None,
            "track_deg": track,
            "on_ground": bool(on_gnd),
            "dist_km": dist_km
        })
    out.sort(key=lambda x: x["dist_km"])
    return out


def fetch_last_route_for_aircraft(icao24_hex):
    if not OS_USER or not OS_PASS:
        return (None, None)
    now = int(datetime.now(timezone.utc).timestamp())
    begin = now - 48 * 3600
    params = {"icao24": icao24_hex.lower(), "begin": begin, "end": now}
    try:
        r = requests.get(OS_FLIGHTS_AC, params=params, auth=(OS_USER, OS_PASS), timeout=20)
        if r.status_code == 404:
            return (None, None)
        r.raise_for_status()
        flights = r.json() or []
        if not flights:
            return (None, None)
        flights.sort(key=lambda f: f.get("lastSeen", 0), reverse=True)
        f = flights[0]
        return (f.get("estDepartureAirport"), f.get("estArrivalAirport"))
    except requests.RequestException:
        return (None, None)


def pretty_print_list(flights, max_results):
    print("\nErgebnis (einmalig):")
    print("Dist(km) |    Callsign    |         Speed        |       Altitude       | Track | Von->Bis")
    print("---------+----------------+----------------------+----------------------+-------+---------")
    shown = 0
    for f in flights:
        cs = f["callsign"] or "(unbekannt)"
        spd = f["vel_kt"]
        alt = f["alt_ft"]
        trk = f["track_deg"]
        spd_txt = f"{spd:.0f} kt / {f['vel_kmh']:.0f} km/h" if spd is not None else "-"
        alt_txt = f"{alt:.0f} ft / {f['alt_m']:.0f} m" if alt is not None and f["alt_m"] is not None else ("ground" if f["on_ground"] else "-")
        trk_txt = f"{trk:.0f}°" if isinstance(trk, (int, float)) else "-"
        dep, arr = fetch_last_route_for_aircraft(f["icao24"])
        dep_arr_txt = f"{dep or '?'}-> {arr or '?'}" if dep or arr else "-"
        print(f" {f['dist_km']:7.1f} | {cs:14s} | {spd_txt:20s} | {alt_txt:20s} | {trk_txt:5s} | {dep_arr_txt}")
        shown += 1
        if shown >= max_results:
            break


def pretty_print_single(nearest):
    f = nearest
    cs = f["callsign"] or "(unbekannt)"
    spd = f["vel_kt"]
    alt = f["alt_ft"]
    trk = f["track_deg"]
    spd_txt = f"{spd:.0f} kt / {f['vel_kmh']:.0f} km/h" if spd is not None else "-"
    alt_txt = f"{alt:.0f} ft / {f['alt_m']:.0f} m" if alt is not None and f["alt_m"] is not None else ("ground" if f["on_ground"] else "-")
    trk_txt = f"{trk:.0f}°" if isinstance(trk, (int, float)) else "-"
    dep, arr = fetch_last_route_for_aircraft(f["icao24"])
    dep_arr_txt = f"{dep or '?'}-> {arr or '?'}" if dep or arr else "-"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("\n[" + ts + "] Nächstes Flugzeug:")
    print("Dist(km) |   Callsign   | Speed                |      Altitude      | Track | Von->Bis")
    print("---------+--------------+----------------------+--------------------+-------+---------")
    print(f" {f['dist_km']:7.1f} | {cs:12s} | {spd_txt:20s} | {alt_txt:18s} | {trk_txt:5s} | {dep_arr_txt}")


def input_float(prompt, default):
    txt = input(f"{prompt} [{default}]: ").strip()
    if not txt:
        return default
    try:
        return float(txt.replace(",", "."))
    except ValueError:
        print("Ungültige Zahl, benutze Default.")
        return default


def input_int(prompt, default):
    txt = input(f"{prompt} [{default}]: ").strip()
    if not txt:
        return default
    try:
        return int(txt)
    except ValueError:
        print("Ungültige Zahl, benutze Default.")
        return default


def main():
    global CENTER_LAT, CENTER_LON, RADIUS_KM, MAX_RESULTS
    print("=== Nearby Flights — Auswahl ===")
    CENTER_LAT = input_float("Deine Breitengrad (lat)", CENTER_LAT)
    CENTER_LON = input_float("Deine Längengrad (lon)", CENTER_LON)
    RADIUS_KM  = input_float("Suchradius in km", RADIUS_KM)

    print("\nModus wählen:")
    print("  1 = Einmalig: Liste der nächsten Flugzeuge")
    print("  2 = Laufend:  Zeige alle X Sekunden das nächstgelegene Flugzeug")
    mode = input_int("Modus (1/2)", 1)

    if mode == 1:
        MAX_RESULTS = input_int("Wie viele Ergebnisse anzeigen?", MAX_RESULTS)
        print("\nHole Daten (einmalig)...")
        flights = fetch_states_nearby(CENTER_LAT, CENTER_LON, RADIUS_KM)
        if not flights:
            print("Keine Flugzeuge gefunden (API leer / Rate-Limit / kein Traffic).")
            return
        pretty_print_list(flights, MAX_RESULTS)
    else:
        interval = input_int("Intervall in Sekunden (z.B. 30)", 30)
        print(f"\nStarte laufenden Modus: prüfe alle {interval}s (Strg+C zum Stoppen).")
        try:
            while True:
                flights = fetch_states_nearby(CENTER_LAT, CENTER_LON, RADIUS_KM)
                if not flights:
                    print(".", end="", flush=True)
                else:
                    nearest = flights[0]
                    pretty_print_single(nearest)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nLaufender Modus beendet.")


if __name__ == "__main__":
    main()
