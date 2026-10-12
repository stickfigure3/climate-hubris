"""PIOMAS Arctic sea ice volume (Polar Science Center, University of Washington)."""

from __future__ import annotations

import csv
import gzip
import io
import logging
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import httpx

from ..config import settings
from ..store import Store

log = logging.getLogger(__name__)

BASE = "https://psc.apl.uw.edu/wordpress/wp-content/uploads/schweiger/ice_volume"
MONTHLY_URL = f"{BASE}/PIOMAS.monthly.Current.v2.1.csv"
# The daily file is renamed every January to carry the current year.
DAILY_URL = BASE + "/PIOMAS.vol.daily.1979.{year}.Current.v2.1.dat.gz"

MISSING = -1.0


def parse_monthly(text: str) -> dict[int, list[float | None]]:
    """year -> 12 monthly mean volumes; months not yet published are None."""
    out: dict[int, list[float | None]] = {}
    rows = csv.reader(io.StringIO(text))
    next(rows)  # header
    for row in rows:
        if len(row) < 13:
            continue
        values = [float(v) for v in row[1:13]]
        out[int(float(row[0]))] = [None if v <= MISSING else v for v in values]
    return out


def parse_daily(text: str) -> dict[int, list[float]]:
    """year -> daily volumes indexed by day number - 1. PIOMAS uses a 365-day calendar."""
    out: dict[int, list[float]] = {}
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 3:
            continue
        year, day, volume = int(parts[0]), int(parts[1]), float(parts[2])
        series = out.setdefault(year, [])
        if day != len(series) + 1:
            raise ValueError(f"PIOMAS daily file skips from day {len(series)} to {day} in {year}")
        series.append(volume)
    return out


def day_to_date(year: int, day: int) -> date:
    """Day number on PIOMAS's 365-day calendar -> calendar date (29 Feb never occurs)."""
    d = date(2001, 1, 1) + timedelta(days=day - 1)  # 2001 is not a leap year
    return date(year, d.month, d.day)


def _last_modified(response: httpx.Response) -> str | None:
    header = response.headers.get("last-modified")
    if not header:
        return None
    return parsedate_to_datetime(header).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ingest(store: Store, client: httpx.Client | None = None) -> dict:
    client = client or httpx.Client(
        headers={"User-Agent": settings.user_agent}, timeout=60, follow_redirects=True
    )

    response = client.get(MONTHLY_URL)
    response.raise_for_status()
    monthly = parse_monthly(response.text)
    store.put_many("PIOMAS_MONTHLY", {str(y): {"values": v} for y, v in monthly.items()})
    latest_year = max(y for y, v in monthly.items() if any(x is not None for x in v))
    latest_month = max(i for i, x in enumerate(monthly[latest_year]) if x is not None) + 1
    store.put_meta(
        "piomas_monthly",
        source="PIOMAS v2.1, Polar Science Center (UW)",
        source_url=MONTHLY_URL,
        source_last_modified=_last_modified(response),
        latest_data=f"{latest_year}-{latest_month:02d}",
        status="ok",
    )

    this_year = datetime.now(timezone.utc).year
    daily_response = None
    for year in (this_year, this_year - 1):
        candidate = client.get(DAILY_URL.format(year=year))
        if candidate.status_code == 200:
            daily_response = candidate
            break
    if daily_response is None:
        store.put_meta("piomas_daily", status="error", detail="Daily volume file not found.")
        raise RuntimeError("PIOMAS daily file not found for this year or last")

    daily = parse_daily(gzip.decompress(daily_response.content).decode("ascii"))
    store.put_many("PIOMAS_DAILY", {str(y): {"values": v} for y, v in daily.items()})
    last_year = max(daily)
    latest_day = day_to_date(last_year, len(daily[last_year]))
    store.put_meta(
        "piomas_daily",
        source="PIOMAS v2.1, Polar Science Center (UW)",
        source_url=str(daily_response.url),
        source_last_modified=_last_modified(daily_response),
        latest_data=latest_day.isoformat(),
        status="ok",
    )
    log.info("PIOMAS ingested: monthly to %s-%02d, daily to %s", latest_year, latest_month, latest_day)
    return {"monthly_years": len(monthly), "daily_latest": latest_day.isoformat()}
