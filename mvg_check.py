"""
check_delay.py
--------------
Checks upcoming S5 departures from Höhenkirchen-Siegertsbrunn
towards Marienplatz using the `mvg` package with SSL fix for Windows.

Install:  pip install mvg aiohttp
Run:      python check_delay.py
"""

import sys
import ssl
import asyncio
import aiohttp
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from mvg import MvgApi, TransportType

LOCAL_TZ = ZoneInfo("Europe/Berlin")

# ── Config ───────────────────────────────────────────────────────────────────
STATION_NAME = "Höhenkirchen-Siegertsbrunn"
TARGET_LINE  = "S5"
DEPARTURES   = 6
# ─────────────────────────────────────────────────────────────────────────────


async def run() -> int:
    now = datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M %Z")
    print(f"🚆  S-Bahn delay check  —  {now}")
    print(f"    Station : {STATION_NAME}  |  Line: {TARGET_LINE}\n")

    # Disable SSL verification — needed on Python 3.14 / Windows
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    connector = aiohttp.TCPConnector(ssl=ssl_ctx)

    async with aiohttp.ClientSession(connector=connector) as session:

        # 1) Resolve station
        print(f"Looking up '{STATION_NAME}'...")
        station = await MvgApi.station_async(STATION_NAME, session=session)
        if not station:
            print("❌  Station not found.", file=sys.stderr)
            return 1
        print(f"  → {station['name']}  (id: {station['id']})\n")

        # 2) Fetch departures
        print("Fetching departures...")
        departures = await MvgApi.departures_async(
            station["id"],
            limit=40,
            offset=0,
            transport_types=[TransportType.SBAHN],
            session=session,
        )

    print(f"  → Total S-Bahn departures: {len(departures)}")
    if departures:
        lines = sorted({d.get("line", "?") for d in departures})
        print(f"  → Lines found: {lines}\n")

    # 3) Filter to S5
    relevant = [d for d in departures if d.get("line") == TARGET_LINE][:DEPARTURES]

    if not relevant:
        print(f"ℹ️  No upcoming {TARGET_LINE} departures found.")
        return 0

    # 4) Print table
    # `planned` and `time` are Unix timestamps in seconds (per mvg package docs)
    print(f"{'Sched':>5}  {'Real':>5}  {'Delay':>6}  {'Destination':<28}  Status")
    print("─" * 72)

    max_delay = 0
    for dep in relevant:
        planned_s  = dep.get("planned", dep.get("time", 0))
        realtime_s = dep.get("time", planned_s)
        delay_min  = max(0, round((realtime_s - planned_s) / 60))
        cancelled  = dep.get("cancelled", False)
        destination = dep.get("destination", "?")

        planned_str  = datetime.fromtimestamp(planned_s,  tz=LOCAL_TZ).strftime("%H:%M")
        realtime_str = datetime.fromtimestamp(realtime_s, tz=LOCAL_TZ).strftime("%H:%M")

        if cancelled:
            status = "🚫 CANCELLED"
        elif delay_min >= 5:
            status = f"⚠️  +{delay_min} min"
            max_delay = max(max_delay, delay_min)
        elif delay_min > 0:
            status = f"🕐 +{delay_min} min"
            max_delay = max(max_delay, delay_min)
        else:
            status = "✅ on time"

        print(f"{planned_str:>5}  {realtime_str:>5}  {delay_min:>+5}m  {destination:<28}  {status}")

    print()
    if max_delay >= 5:
        print(f"⚠️  Max delay on {TARGET_LINE}: {max_delay} min")
    else:
        print(f"✅  {TARGET_LINE} running on time (max delay: {max_delay} min)")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))