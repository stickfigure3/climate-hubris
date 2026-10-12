"""Rainfall from ClimateSERV (NASA SERVIR), using the CHIRPS dataset.

ClimateSERV is asynchronous: submit a request, poll its progress, then fetch the
result. We ask for the daily area-average rainfall over the box of each region
and subregion and store it as monthly totals.
"""

from __future__ import annotations

import calendar
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import httpx

from ..config import settings
from ..regions import AREAS, Region, Subregion
from ..store import Store

log = logging.getLogger(__name__)

API = "https://climateserv.servirglobal.net/api"
SEED_PATH = Path(__file__).resolve().parents[2] / "seed" / "rainfall_history.json"
CHIRPS = 0  # ClimateSERV datatype id: UCSB CHIRPS rainfall, 0.05 degree
AVERAGE = 5  # operation type: spatial average

# First year of the record we keep. 1991-2020 is the WMO standard normal period.
HISTORY_START = 1991
BASELINE = (1991, 2020)
# ClimateSERV takes ~25 s per year of daily data for a region's box (~5 s for a subregion's)
# and fails outright on 30-year requests, so history is fetched in pieces.
CHUNK_YEARS = 5
# Requests in flight at once. ClimateSERV queues more than this rather than running them.
WORKERS = 4


class ClimateServError(RuntimeError):
    pass


def fetch_daily(
    client: httpx.Client, region: Region | Subregion, start: date, end: date, timeout_s: float = 300
) -> list[tuple[date, float]]:
    """Daily area-average rainfall (mm) over a box. Days without data are omitted."""
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
    """Write the bundled rainfall history into any region or subregion that has none stored yet."""
    if not path.exists():
        return 0
    seed = json.loads(path.read_text())["regions"]
    written = 0
    for region_id, months in seed.items():
        if region_id in AREAS and not store.query(f"RAIN#{region_id}"):
            store.put_many(f"RAIN#{region_id}", months)
            written += len(months)
    return written


def _next_start(store: Store, region: Region | Subregion) -> date:
    """Resume after the last fully observed month already stored."""
    complete = [i["sk"] for i in store.query(f"RAIN#{region.id}") if i.get("complete")]
    if not complete:
        return date(HISTORY_START, 1, 1)
    year, month = int(complete[-1][:4]), int(complete[-1][5:])
    return date(year + (month == 12), month % 12 + 1, 1)


def _fetch_since(
    client: httpx.Client, area: Region | Subregion, start: date, today: date, seconds_left: Callable[[], float]
) -> tuple[dict[str, dict], bool, str | None]:
    """Months from `start` to today, in CHUNK_YEARS pieces: (months, finished, error)."""
    months: dict[str, dict] = {}
    while start <= today:
        if seconds_left() < 330:
            return months, False, None
        end = min(date(start.year + CHUNK_YEARS - 1, 12, 31), today)
        try:
            months.update(to_monthly(fetch_daily(client, area, start, end)))
        except (ClimateServError, httpx.HTTPError, ValueError, KeyError) as exc:
            return months, False, f"{exc.__class__.__name__}: {exc}"
        start = end + timedelta(days=1)
    return months, True, None


def ingest(
    store: Store,
    client: httpx.Client | None = None,
    today: date | None = None,
    seconds_left: Callable[[], float] | None = None,
) -> dict:
    """Bring every region and subregion up to date.

    History before the current year normally comes from the bundled seed file
    (see load_seed). Anything missing is fetched in CHUNK_YEARS pieces, a few
    boxes at a time; the run stops early if time is running out and reports
    `complete: False`, and the next run resumes where this one stopped. One box
    failing does not stop the others.
    """
    client = client or httpx.Client(
        headers={"User-Agent": settings.user_agent}, timeout=120, follow_redirects=True
    )
    today = today or date.today()
    seconds_left = seconds_left or (lambda: float("inf"))
    summary: dict = {"regions": {}, "complete": True, "seeded_months": load_seed(store), "errors": 0}
    latest_overall: str | None = None

    # Fetching is the slow part and runs on threads; the table is only touched from this one.
    starts = {area.id: _next_start(store, area) for area in AREAS.values()}
    # Furthest behind first, so a run that is cut short still helps the boxes that need it most.
    queue = sorted(AREAS.values(), key=lambda area: starts[area.id])
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        fetches = {
            area.id: pool.submit(_fetch_since, client, area, starts[area.id], today, seconds_left)
            for area in queue
        }
        for area_id, fetch in fetches.items():
            months, finished, error = fetch.result()
            if months:
                store.put_many(f"RAIN#{area_id}", months)
            if not finished:
                summary["complete"] = False
            if error:
                summary["errors"] += 1
                log.warning("rainfall %s failed: %s", area_id, error)

            stored = store.query(f"RAIN#{area_id}")
            latest = stored[-1]["sk"] if stored else None
            summary["regions"][area_id] = {"months_written": len(months), "latest": latest}
            if error:
                summary["regions"][area_id]["error"] = error
            if latest and (latest_overall is None or latest < latest_overall):
                latest_overall = latest
            log.info("rainfall %s: wrote %d months, latest %s", area_id, len(months), latest)

    store.put_meta(
        "monsoon_rainfall",
        source="CHIRPS via ClimateSERV (NASA SERVIR)",
        source_url="https://climateserv.servirglobal.net",
        latest_data=latest_overall,
        areas=len(AREAS),
        areas_failed=summary["errors"],
        status="ok" if summary["complete"] else "backfilling",
    )
    return summary
