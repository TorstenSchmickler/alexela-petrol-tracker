#!/usr/bin/env python3
"""Track Alexela 95 petrol prices (Estonia) and report the 7-day low.

Source: https://xydata.ee/kutus/alexela (Alexela's own site doesn't serve prices as HTML).
Data is kept in data/prices.json, committed by the hourly GitHub Action and read by index.html.

Usage:
  petrol_tracker.py fetch    # grab current price + daily history, update data/prices.json
  petrol_tracker.py report   # print 7-day low (default)
"""
import json
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

URL = "https://xydata.ee/kutus/alexela"
DATA_PATH = Path(__file__).resolve().parent / "data" / "prices.json"
TZ = ZoneInfo("Europe/Tallinn")


def load():
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text())
    return {"source": URL, "fuel": "Alexela 95", "updated": None, "readings": [], "daily": {}}


def save(data):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


def download():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 petrol-tracker"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def parse(html):
    card = re.search(r"95 bensiin</b>.*?<span class=\"price\">([\d.]+)</span>", html, re.S)
    if not card:
        raise ValueError("current 95 price not found - page layout may have changed")
    current = float(card.group(1))

    # Table rows: <td class="tleft">DD.MM.YYYY</td> <td>95 €</td> <td>98 €</td>
    table_start = html.find("<th>Alexela 95 bensiin</th>")
    table_end = html.find("</table>", table_start)
    daily = {}
    if table_start != -1:
        for d, p in re.findall(r'<td class="tleft">(\d{2}\.\d{2}\.\d{4})</td>\s*<td>([\d.]+) €</td>',
                               html[table_start:table_end]):
            daily[datetime.strptime(d, "%d.%m.%Y").date().isoformat()] = float(p)
    return current, daily


def fetch():
    current, daily = parse(download())
    now = datetime.now(TZ).isoformat(timespec="minutes")
    data = load()
    data["readings"].append({"t": now, "p": current})
    data["daily"].update(daily)
    data["updated"] = now
    save(data)
    print(f"{now}  Alexela 95: {current:.3f} €/l  ({len(daily)} daily rows synced)")


def seven_day_low(data, today):
    """Lowest price from today and the previous 6 days, across daily and hourly data."""
    start = (today - timedelta(days=6)).isoformat()
    candidates = [(p, d, "daily") for d, p in data["daily"].items() if d >= start]
    candidates += [(r["p"], r["t"], "hourly") for r in data["readings"] if r["t"][:10] >= start]
    return min(candidates) if candidates else None


def report():
    data = load()
    today = datetime.now(TZ).date()
    low = seven_day_low(data, today)
    if not low:
        print("No data from the last 7 days yet - run `fetch` first.")
        return
    start = (today - timedelta(days=6)).isoformat()
    print("Alexela 95 - last 7 days (daily):")
    for d in sorted(k for k in data["daily"] if k >= start):
        print(f"  {d}  {data['daily'][d]:.3f} €/l")
    if data["readings"]:
        last = data["readings"][-1]
        print(f"Latest reading: {last['p']:.3f} €/l at {last['t']}")
    print(f"7-day LOW:      {low[0]:.3f} €/l on {low[1]} ({low[2]})")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"fetch": fetch, "report": report}.get(cmd, lambda: sys.exit(__doc__))()
