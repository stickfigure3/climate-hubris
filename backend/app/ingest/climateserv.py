"""Regional rainfall from ClimateSERV (NASA SERVIR), using the CHIRPS dataset.

ClimateSERV is asynchronous: submit a request, poll its progress, then fetch the
result. We ask for the daily area-average rainfall over a region's polygon and
store it as monthly totals.
"""

from __future__ import annotations

import calendar
import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import httpx

from ..config import settings
from ..regions import REGIONS, Region
from ..store import Store

log = logging.getLogger(__name__)

API = "https://climateserv.servirglobal.net/api"
SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "rainfall_history.json"
CHIRPS = 0  # ClimateSERV datatype id: UCSB CHIRPS rainfall, 0.05 degree
AVERAGE = 5  # operation type: spatial average

# First year of the record we keep. 1991-2020 is the WMO standard normal period.
HISTORY_START = 1991
BASELINE = (1991, 2020)
# ClimateSERV takes ~25 s per year of daily data for these polygons and fails outright on
# 30-year requests, so history is fetched in pieces.
CHUNK_YEARS = 5


class ClimateServError(RuntimeError):
    pass


def fetch_daily(
    client: httpx.Client, region: Region, start: date, end: date, timeout_s: float = 300
) -> list[tuple[date, float]]:
    """Daily area-average rainfall (mm) for a region. Days without data are omitted."""
    params = {
        "datatype": CHIRPS,
        "begintime": start.strftime("%m/%d/%Y"),
        "endtime": end.strftime("%m/%d/%Y"),
        "intervaltype": 0,  # daily
        "operationtype": AVERAGE,
        "dateType_Category": "default",
        "isZip_CurrentDataType": "false",
        "geometry": json.dumps(region.polygon),
    }
    response = client.get(f"{API}/submitDataRequest/", params=params)
    response.raise_for_status()
    request_id = response.json()[0]

    deadline = time.monotonic() + timeout_s
    while True:
        progress = client.get(f"{API}/getDataRequestProgress/", params={"id": request_id}).json()[0]
        if progress < 0:
            raise ClimateServError(f"ClimateSERV request {request_id} failed for {region.id}")
        if progress >= 100:
            break
        if time.monotonic() > deadline:
            raise ClimateServError(f"ClimateSERV request {request_id} timed out at {progress}%")
        time.sleep(3)

    rows = client.get(f"{API}/getDataFromRequest/", params={"id": request_id}).json()["data"]
    out = []
    for row in rows:
        value = row["value"]["avg"]
        # Missing days come back as null or a large negative fill value.
        if value is None or value < 0:
            continue
        out.append((date(row["year"], row["month"], row["day"]), float(value)))
    return out


def to_monthly(daily: list[tuple[date, float]]) -> dict[str, dict]:
    """Aggregate to "YYYY-MM" -> {total_mm, days, complete}."""
    months: dict[str, dict] = {}
    for day, mm in daily:
        m = months.setdefault(f"{day.year}-{day.month:02d}", {"total_mm": 0.0, "days": 0})
        m["total_mm"] += mm
        m["days"] += 1
    for key, m in months.items():
        year, month = int(key[:4]), int(key[5:])
        m["complete"] = m["days"] == calendar.monthrange(year, month)[1]
    return months


def load_seed(store: Store, path: Path = SEED_PATH) -> int:
    """Write the bundled rainfall history into any region that has none stored yet."""
    if not path.exists():
        return 0
    seed = json.loads(path.read_text())["regions"]
    written = 0
    for region_id, months in seed.items():
        if region_id in REGIONS and not store.query(f"RAIN#{region_id}"):
            store.put_many(f"RAIN#{region_id}", months)
            written += len(months)
    return written


def _next_start(store: Store, region: Region) -> date:
    """Resume after the last fully observed month already stored."""
    complete = [i["sk"] for i in store.query(f"RAIN#{region.id}") if i.get("complete")]
    if not complete:
        return date(HISTORY_START, 1, 1)
    year, month = int(complete[-1][:4]), int(complete[-1][5:])
    return date(year + (month == 12), month % 12 + 1, 1)


def ingest(
    store: Store,
    client: httpx.Client | None = None,
    today: date | None = None,
    seconds_left: Callable[[], float] | None = None,
) -> dict:
    """Bring every region up to date.

    History before the current year normally comes from the bundled seed file
    (see load_seed). Anything missing is fetched in CHUNK_YEARS pieces; the run
    stops early if time is running out and reports `complete: False`, and the
    next run resumes where this one stopped.
    """
    client = client or httpx.Client(
        headers={"User-Agent": settings.user_agent}, timeout=120, follow_redirects=True
    )
    today = today or date.today()
    seconds_left = seconds_left or (lambda: float("inf"))
    summary: dict = {"regions": {}, "complete": True, "seeded_months": load_seed(store)}
    latest_overall: str | None = None

    for region in REGIONS.values():
        start = _next_start(store, region)
        written = 0
        while start <= today:
            if seconds_left() < 330:
                summary["complete"] = False
                break
            end = min(date(start.year + CHUNK_YEARS - 1, 12, 31), today)
            months = to_monthly(fetch_daily(client, region, start, end))
            if months:
                store.put_many(f"RAIN#{region.id}", months)
                written += len(months)
            start = end + timedelta(days=1)

        stored = store.query(f"RAIN#{region.id}")
        latest = stored[-1]["sk"] if stored else None
        summary["regions"][region.id] = {"months_written": written, "latest": latest}
        if latest and (latest_overall is None or latest < latest_overall):
            latest_overall = latest
        log.info("rainfall %s: wrote %d months, latest %s", region.id, written, latest)

    store.put_meta(
        "monsoon_rainfall",
        source="CHIRPS via ClimateSERV (NASA SERVIR)",
        source_url="https://climateserv.servirglobal.net",
        latest_data=latest_overall,
        status="ok" if summary["complete"] else "backfilling",
    )
    return summary
