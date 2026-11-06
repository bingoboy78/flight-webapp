import os
import json
import asyncio
import uuid
import urllib.request
import sqlite3
from datetime import datetime, timedelta
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv
from telegram import Bot

from fast_flights import FlightQuery, Passengers, create_query, get_flights

load_dotenv()

APP_PASSWORD = os.getenv("APP_PASSWORD", "flyhub2027")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DB_PATH = "flighthub.db"

# In-memory task progress store
tasks = {}

# --- Database ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS searches (
        id TEXT PRIMARY KEY,
        created_at TEXT,
        params TEXT,
        results TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS monitors (
        id TEXT PRIMARY KEY,
        route TEXT,
        created_at TEXT,
        is_active INTEGER DEFAULT 1,
        last_price REAL,
        last_check TEXT
    )""")
    conn.commit()
    conn.close()

def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# --- Helpers ---
def get_usd_rate():
    try:
        url = "https://open.er-api.com/v6/latest/ILS"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data["rates"]["USD"]
    except Exception:
        return 0.27

def to_usd(amount, currency):
    if not amount:
        return 0.0
    c = str(currency or "USD").upper()
    if c == "USD":
        return float(amount)
    if c == "ILS":
        return float(amount) * get_usd_rate()
    if c == "EUR":
        return float(amount) * 1.08
    if c == "GBP":
        return float(amount) * 1.28
    return float(amount)

def to_ils(amount, currency):
    usd_val = to_usd(amount, currency)
    rate = get_usd_rate()
    if rate > 0:
        return round(usd_val / rate, 0)
    return round(usd_val * 3.7, 0)

def make_google_flights_url(origin, dest, date, return_date=None):
    if return_date:
        return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{date}%20through%20{return_date}"
    return f"https://www.google.com/travel/flights?q=Flights%20from%20{origin}%20to%20{dest}%20on%20{date}"

def get_airport(code):
    return code.upper() if code else None

POPULAR_AIRPORTS = [
    {"code": "TLV", "name": "Tel Aviv"},
    {"code": "HKG", "name": "Hong Kong"},
    {"code": "SIN", "name": "Singapore"},
    {"code": "BKK", "name": "Bangkok"},
    {"code": "NRT", "name": "Tokyo Narita"},
    {"code": "ICN", "name": "Seoul"},
    {"code": "KUL", "name": "Kuala Lumpur"},
    {"code": "IST", "name": "Istanbul"},
    {"code": "BCN", "name": "Barcelona"},
    {"code": "CDG", "name": "Paris"},
    {"code": "FCO", "name": "Rome"},
    {"code": "LHR", "name": "London"},
    {"code": "JFK", "name": "New York"},
    {"code": "ATH", "name": "Athens"},
    {"code": "AMS", "name": "Amsterdam"},
    {"code": "DXB", "name": "Dubai"},
    {"code": "MLE", "name": "Maldives"},
    {"code": "CMB", "name": "Colombo"},
    {"code": "DEL", "name": "Delhi"},
    {"code": "MNL", "name": "Manila"},
    {"code": "TPE", "name": "Taipei"},
    {"code": "PEK", "name": "Beijing"},
    {"code": "LAX", "name": "Los Angeles"},
    {"code": "MIA", "name": "Miami"},
    {"code": "PRG", "name": "Prague"},
    {"code": "VIE", "name": "Vienna"},
    {"code": "ZRH", "name": "Zurich"},
]

def is_regional(origin, dest):
    asia = {"HKG", "SIN", "BKK", "NRT", "ICN", "KUL", "MNL", "TPE", "PEK", "CMB", "DEL"}
    europe = {"BCN", "CDG", "FCO", "LHR", "ATH", "AMS", "PRG", "VIE", "ZRH", "IST"}
    if origin in asia and dest in asia:
        return True
    if origin in europe and dest in europe:
        return True
    return False

import re

def sanitize_date(date_str):
    """Ensure date is valid YYYY-MM-DD format."""
    m = re.match(r'(\d+)-(\d{1,2})-(\d{1,2})', str(date_str))
    if m:
        year = int(m.group(1))
        if year > 2100:  # Catch locale bugs like 12027 -> 2027
            year = year % 10000
        month = int(m.group(2))
        day = int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"
    return date_str

def search_flight(origin_code, dest_code, date_str, direct_only=False):
    date_str = sanitize_date(date_str)
    regional = is_regional(origin_code, dest_code)
    max_stops = 0 if (direct_only or regional) else 1

    query = create_query(
        flights=[FlightQuery(date=date_str, from_airport=str(origin_code).upper(), to_airport=str(dest_code).upper())],
        trip="one-way",
        currency="USD",
        max_stops=max_stops
    )

    try:
        results = get_flights(query)
        if not results:
            return None

        valid_results = [f for f in results if getattr(f, "price", None) and getattr(f, "flights", None)]
        if not valid_results:
            return None

        best = min(valid_results, key=lambda f: f.price)

        legs_info = []
        for idx, leg in enumerate(best.flights):
            airline_name = ""
            if best.airlines:
                airline_name = best.airlines[idx] if idx < len(best.airlines) else best.airlines[0]
            elif getattr(best, "type", None):
                airline_name = best.type

            dep_str = ""
            arr_str = ""
            if hasattr(leg, "departure") and leg.departure:
                dep_str = f"{leg.departure.date[0]:04d}-{leg.departure.date[1]:02d}-{leg.departure.date[2]:02d} {leg.departure.time[0]:02d}:{leg.departure.time[1]:02d}"
            if hasattr(leg, "arrival") and leg.arrival:
                arr_str = f"{leg.arrival.date[0]:04d}-{leg.arrival.date[1]:02d}-{leg.arrival.date[2]:02d} {leg.arrival.time[0]:02d}:{leg.arrival.time[1]:02d}"

            legs_info.append({
                "airline": airline_name,
                "flight_number": leg.plane_type or (getattr(best, "type", "") or ""),
                "dep_airport": leg.from_airport.name or leg.from_airport.code,
                "arr_airport": leg.to_airport.name or leg.to_airport.code,
                "dep_time": dep_str,
                "arr_time": arr_str
            })

        layover_info = None
        dur_min = sum(getattr(f, "duration", 0) for f in best.flights)
        if len(best.flights) > 1:
            f0 = best.flights[0]
            f1 = best.flights[1]
            try:
                dt0 = datetime(*f0.arrival.date, *f0.arrival.time)
                dt1 = datetime(*f1.departure.date, *f1.departure.time)
                lay_dur = int((dt1 - dt0).total_seconds() // 60)
                layover_info = {
                    "airport": f0.to_airport.name or f0.to_airport.code,
                    "duration_min": lay_dur
                }
                if lay_dur > 0:
                    dur_min += lay_dur
            except Exception:
                pass

        currency = "USD"
        raw_price = float(best.price)
        price_usd = round(to_usd(raw_price, currency), 0)
        price_ils = to_ils(raw_price, currency)

        return {
            "raw_price": raw_price,
            "currency": currency,
            "price_ils": price_ils,
            "price_usd": price_usd,
            "duration_min": dur_min,
            "stops": len(best.flights) - 1,
            "legs": legs_info,
            "layover": layover_info,
            "regional": regional,
            "booking_url": make_google_flights_url(origin_code, dest_code, date_str)
        }
    except Exception:
        pass
    return None


# --- App ---
@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/airports")
async def airports():
    return POPULAR_AIRPORTS


@app.post("/api/search")
async def start_search(request: Request):
    body = await request.json()
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "progress": 0, "results": None, "total_steps": 0, "current_step": 0}

    asyncio.create_task(run_search(task_id, body))
    return {"task_id": task_id}


async def run_search(task_id, params):
    cities = params.get("cities", [])
    mode = params.get("mode", "specific")
    direct_only = params.get("direct_only", False)
    usd_rate = get_usd_rate()

    origin = "TLV"

    if mode == "specific":
        legs_input = params.get("legs", [])
        total_steps = len(legs_input)
        tasks[task_id]["total_steps"] = total_steps
        tasks[task_id]["status"] = "running"

        results_legs = []
        total_usd = 0
        total_ils = 0
        international_usd = 0
        internal_usd = 0

        for i, leg in enumerate(legs_input):
            tasks[task_id]["current_step"] = i + 1
            tasks[task_id]["progress"] = int((i / total_steps) * 100)

            result = await asyncio.to_thread(
                search_flight, leg["from"], leg["to"], leg["date"], direct_only
            )
            if result:
                total_usd += result["price_usd"]
                total_ils += result["price_ils"]
                if result["regional"]:
                    internal_usd += result["price_usd"]
                else:
                    international_usd += result["price_usd"]
                result["from"] = leg["from"]
                result["to"] = leg["to"]
                result["date"] = leg["date"]
                results_legs.append(result)
            else:
                results_legs.append({
                    "from": leg["from"],
                    "to": leg["to"],
                    "date": leg["date"],
                    "booking_url": make_google_flights_url(leg["from"], leg["to"], leg["date"]),
                    "error": "No flights found"
                })

        booking_url = None
        if len(results_legs) == 2 and results_legs[0].get("from") == results_legs[1].get("to") and results_legs[0].get("to") == results_legs[1].get("from"):
            booking_url = make_google_flights_url(results_legs[0]["from"], results_legs[0]["to"], results_legs[0]["date"], results_legs[1]["date"])
        elif results_legs:
            booking_url = results_legs[0].get("booking_url")

        combo = {
            "total_ils": total_ils,
            "total_usd": total_usd,
            "international_usd": international_usd,
            "internal_usd": internal_usd,
            "booking_url": booking_url,
            "legs": results_legs
        }
        tasks[task_id]["results"] = [combo]
        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "done"

        # Save to history
        save_search(task_id, params, [combo])

    elif mode == "flexible":
        month = int(params.get("month", 1))
        year = int(params.get("year", 2027))
        min_days = int(params.get("min_trip", 12))
        max_days = int(params.get("max_trip", 14))
        min_stay = int(params.get("min_stay", 3))

        route = [origin] + cities + [origin]
        num_legs = len(route) - 1

        # Build date ranges for each leg
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]

        # Fetch prices for all legs across the month
        tasks[task_id]["status"] = "running"
        tasks[task_id]["total_steps"] = num_legs
        all_prices = {}

        for leg_idx in range(num_legs):
            o = route[leg_idx]
            d = route[leg_idx + 1]
            tasks[task_id]["current_step"] = leg_idx + 1
            leg_key = f"{o}_{d}"
            all_prices[leg_key] = {}

            for day in range(1, days_in_month + 1):
                date_str = f"{year}-{month:02d}-{day:02d}"
                tasks[task_id]["progress"] = int(
                    ((leg_idx * days_in_month + day) / (num_legs * days_in_month)) * 100
                )
                result = await asyncio.to_thread(search_flight, o, d, date_str, direct_only)
                if result:
                    all_prices[leg_key][date_str] = result

        # Find best combinations
        combos = []
        for d1 in range(1, days_in_month + 1):
            d1_str = f"{year}-{month:02d}-{d1:02d}"
            key0 = f"{route[0]}_{route[1]}"
            if d1_str not in all_prices.get(key0, {}):
                continue

            if num_legs == 3:
                for d2 in range(d1 + min_stay, min(d1 + 9, days_in_month + 1)):
                    d2_str = f"{year}-{month:02d}-{d2:02d}"
                    key1 = f"{route[1]}_{route[2]}"
                    if d2_str not in all_prices.get(key1, {}):
                        continue
                    for d3 in range(d2 + min_stay, min(d2 + 9, days_in_month + 1)):
                        d3_str = f"{year}-{month:02d}-{d3:02d}"
                        key2 = f"{route[2]}_{route[3]}"
                        if d3_str not in all_prices.get(key2, {}):
                            continue
                        total_days = d3 - d1
                        if min_days <= total_days <= max_days:
                            f0 = all_prices[key0][d1_str]
                            f1 = all_prices[key1][d2_str]
                            f2 = all_prices[key2][d3_str]
                            total_usd = f0["price_usd"] + f1["price_usd"] + f2["price_usd"]
                            total_ils = f0["price_ils"] + f1["price_ils"] + f2["price_ils"]
                            intl_usd = sum(f["price_usd"] for f in [f0, f1, f2] if not f["regional"])
                            intrnl_usd = sum(f["price_usd"] for f in [f0, f1, f2] if f["regional"])
                            legs_out = []
                            for f, dt, o2, d2x in [(f0, d1_str, route[0], route[1]),
                                                    (f1, d2_str, route[1], route[2]),
                                                    (f2, d3_str, route[2], route[3])]:
                                fc = dict(f)
                                fc["from"] = o2
                                fc["to"] = d2x
                                fc["date"] = dt
                                legs_out.append(fc)
                            combos.append({
                                "total_ils": total_ils,
                                "total_usd": total_usd,
                                "international_usd": intl_usd,
                                "internal_usd": intrnl_usd,
                                "booking_url": f0.get("booking_url"),
                                "days": total_days,
                                "legs": legs_out
                            })

            elif num_legs == 2:
                for d2 in range(d1 + min_stay, min(d1 + max_days + 1, days_in_month + 1)):
                    d2_str = f"{year}-{month:02d}-{d2:02d}"
                    key1 = f"{route[1]}_{route[2]}"
                    if d2_str not in all_prices.get(key1, {}):
                        continue
                    total_days = d2 - d1
                    if min_days <= total_days <= max_days:
                        f0 = all_prices[key0][d1_str]
                        f1 = all_prices[key1][d2_str]
                        total_usd = f0["price_usd"] + f1["price_usd"]
                        total_ils = f0["price_ils"] + f1["price_ils"]
                        legs_out = []
                        for f, dt, o2, d2x in [(f0, d1_str, route[0], route[1]),
                                                (f1, d2_str, route[1], route[2])]:
                            fc = dict(f)
                            fc["from"] = o2
                            fc["to"] = d2x
                            fc["date"] = dt
                            legs_out.append(fc)
                        combos.append({
                            "total_ils": total_ils,
                            "total_usd": total_usd,
                            "international_usd": total_usd,
                            "internal_usd": 0,
                            "booking_url": make_google_flights_url(route[0], route[1], d1_str, d2_str),
                            "days": total_days,
                            "legs": legs_out
                        })

        combos.sort(key=lambda x: x["total_usd"])
        top5 = combos[:5]
        tasks[task_id]["results"] = top5
        tasks[task_id]["progress"] = 100
        tasks[task_id]["status"] = "done"
        save_search(task_id, params, top5)


def save_search(task_id, params, results):
    conn = db_conn()
    conn.execute(
        "INSERT INTO searches (id, created_at, params, results) VALUES (?, ?, ?, ?)",
        (task_id, datetime.now().isoformat(), json.dumps(params), json.dumps(results))
    )
    conn.commit()
    conn.close()


@app.get("/api/search/stream/{task_id}")
async def stream_progress(task_id: str):
    async def event_generator():
        while True:
            if task_id not in tasks:
                yield {"data": json.dumps({"error": "Task not found"})}
                break
            t = tasks[task_id]
            yield {"data": json.dumps({
                "status": t["status"],
                "progress": t["progress"],
                "current_step": t.get("current_step", 0),
                "total_steps": t.get("total_steps", 0),
                "results": t.get("results")
            })}
            if t["status"] in ("done", "error"):
                break
            await asyncio.sleep(1)
    return EventSourceResponse(event_generator())


@app.get("/api/history")
async def get_history():
    conn = db_conn()
    rows = conn.execute("SELECT id, created_at, params, results FROM searches ORDER BY created_at DESC LIMIT 50").fetchall()
    conn.close()
    return [{"id": r["id"], "created_at": r["created_at"],
             "params": json.loads(r["params"]), "results": json.loads(r["results"])} for r in rows]


@app.post("/api/monitor")
async def create_monitor(request: Request):
    body = await request.json()
    monitor_id = str(uuid.uuid4())
    conn = db_conn()
    conn.execute(
        "INSERT INTO monitors (id, route, created_at) VALUES (?, ?, ?)",
        (monitor_id, json.dumps(body), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    # Send confirmation to Telegram
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            bot = Bot(TELEGRAM_BOT_TOKEN)
            legs = body.get("legs", [])
            route_str = " > ".join([l.get("from", "?") for l in legs] + [legs[-1].get("to", "?")])
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=f"New flight monitor set!\nRoute: {route_str}\nDates: {legs[0].get('date','')} - {legs[-1].get('date','')}"
            )
        except Exception:
            pass

    return {"id": monitor_id, "status": "created"}


@app.get("/api/monitors")
async def get_monitors():
    conn = db_conn()
    rows = conn.execute("SELECT * FROM monitors WHERE is_active = 1 ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "route": json.loads(r["route"]),
             "created_at": r["created_at"], "last_price": r["last_price"],
             "last_check": r["last_check"]} for r in rows]


@app.delete("/api/monitor/{monitor_id}")
async def delete_monitor(monitor_id: str):
    conn = db_conn()
    conn.execute("UPDATE monitors SET is_active = 0 WHERE id = ?", (monitor_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted"}


@app.post("/api/heatmap")
async def start_heatmap(request: Request):
    body = await request.json()
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "pending", "progress": 0, "results": None}
    asyncio.create_task(run_heatmap(task_id, body))
    return {"task_id": task_id}


async def run_heatmap(task_id, params):
    import calendar
    origin = params.get("origin", "TLV")
    dest = params.get("destination", "HKG")
    month = int(params.get("month", 1))
    year = int(params.get("year", 2027))
    direct_only = params.get("direct_only", False)

    days_in_month = calendar.monthrange(year, month)[1]
    usd_rate = get_usd_rate()
    tasks[task_id]["status"] = "running"
    tasks[task_id]["total_steps"] = days_in_month

    prices = {}
    for day in range(1, days_in_month + 1):
        tasks[task_id]["current_step"] = day
        tasks[task_id]["progress"] = int((day / days_in_month) * 100)
        date_str = f"{year}-{month:02d}-{day:02d}"

        result = await asyncio.to_thread(search_flight, origin, dest, date_str, direct_only)
        if result:
            prices[date_str] = {
                "price_ils": result["price_ils"],
                "price_usd": result["price_usd"],
                "stops": result["stops"],
                "booking_url": result.get("booking_url")
            }

    tasks[task_id]["results"] = {
        "origin": origin,
        "destination": dest,
        "month": month,
        "year": year,
        "prices": prices
    }
    tasks[task_id]["progress"] = 100
    tasks[task_id]["status"] = "done"


@app.post("/api/auth")
async def auth(request: Request):
    body = await request.json()
    if body.get("password") == APP_PASSWORD:
        return {"status": "ok"}
    raise HTTPException(status_code=401, detail="Wrong password")
