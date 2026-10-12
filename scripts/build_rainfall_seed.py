"""Build backend/seed/rainfall_history.json: monthly CHIRPS rainfall per monsoon region and subregion.

Past months never change, so they are fetched once here and shipped with the
repository. A fresh deployment or `docker compose up` then has 35 years of
history immediately instead of spending hours on ClimateSERV requests.

    python scripts/build_rainfall_seed.py            # resumes if interrupted
"""

from __future__ import annotations

import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import settings  # noqa: E402
from app.ingest.climateserv import (  # noqa: E402
    CHUNK_YEARS,
    HISTORY_START,
    SEED_PATH,
    fetch_daily,
    to_monthly,
)
from app.regions import AREAS  # noqa: E402

END_YEAR = date.today().year - 1  # complete calendar years only
# ClimateSERV works through one client's requests one at a time and answers 503 when
# more than a handful are waiting, so more workers than this only produce failures.
WORKERS = 4
ATTEMPTS = 6

_lock = threading.Lock()


def _save(seed: dict, months: dict | None = None, chunk: dict | None = None) -> None:
    with _lock:  # regions are fetched on separate threads but share one file
        if months is not None:
            months.update(chunk)
        SEED_PATH.write_text(json.dumps(seed, separators=(",", ":"), sort_keys=True))


def build_region(region, seed: dict) -> None:
    months = seed["regions"].setdefault(region.id, {})
    client = httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=120)
    for start_year in range(HISTORY_START, END_YEAR + 1, CHUNK_YEARS):
        end_year = min(start_year + CHUNK_YEARS - 1, END_YEAR)
        if f"{end_year}-12" in months:
            continue
        for attempt in range(1, ATTEMPTS + 1):
            try:
                daily = fetch_daily(client, region, date(start_year, 1, 1), date(end_year, 12, 31), timeout_s=900)
                break
            except Exception as exc:
                print(f"{region.id} {start_year}-{end_year} attempt {attempt}: {str(exc)[:120]}", flush=True)
                time.sleep(30 * attempt)  # an overloaded service needs time, not another request
        else:
            raise SystemExit(f"{region.id} {start_year}-{end_year} failed {ATTEMPTS} times")
        chunk = to_monthly(daily)
        _save(seed, months, {k: {**v, "total_mm": round(v["total_mm"], 2)} for k, v in chunk.items()})
        print(f"{region.id} {start_year}-{end_year}: {len(chunk)} months", flush=True)


def main() -> None:
    seed = json.loads(SEED_PATH.read_text()) if SEED_PATH.exists() else {"regions": {}}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for future in [pool.submit(build_region, region, seed) for region in AREAS.values()]:
            future.result()
    seed["source"] = "CHIRPS v2.0 daily area averages via ClimateSERV, summed to months"
    seed["through"] = f"{END_YEAR}-12"
    _save(seed)
    print("done", {k: len(v) for k, v in seed["regions"].items()})


if __name__ == "__main__":
    main()
