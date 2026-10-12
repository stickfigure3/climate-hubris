"""Earth's heat inventory (Indicators of Global Climate Change, Forster et al.).

The inventory is the heat the ocean, land, ice and atmosphere have accumulated since
1971, in ZJ. Its rate of change is Earth's energy imbalance: what comes in minus what
goes out. The satellite record of the two flows themselves (NASA CERES) is only
distributed behind an Earthdata login, so the imbalance is taken from where the
heat ended up instead.
"""

from __future__ import annotations

import csv
import io
import logging

import httpx

from ..config import settings
from ..store import Store

log = logging.getLogger(__name__)

URL = (
    "https://raw.githubusercontent.com/ClimateIndicator/data/main/"
    "data/base/earth_energy_imbalance/earth_energy_imbalance.csv"
)


def parse(text: str) -> dict[int, dict[str, float | None]]:
    """year -> {ocean, total} in ZJ. `total` is None for the newest years, which the
    source publishes for the ocean only."""
    out: dict[int, dict[str, float | None]] = {}
    year: int | None = None
    for row in csv.DictReader(io.StringIO(text)):
        # Rows are stamped mid-year (1971.5); the newest row can arrive without a stamp.
        if row["time"]:
            year = int(float(row["time"]))
        elif year is not None:
            year += 1
        else:
            continue
        if not row["ocean_full-depth"]:
            continue
        out[year] = {
            "ocean": float(row["ocean_full-depth"]),
            "total": float(row["total"]) if row["total"] else None,
        }
    return out


def ingest(store: Store, client: httpx.Client | None = None) -> dict:
    client = client or httpx.Client(
        headers={"User-Agent": settings.user_agent}, timeout=60, follow_redirects=True
    )
    response = client.get(URL)
    response.raise_for_status()
    yearly = parse(response.text)
    store.put_many("HEAT_INVENTORY", {str(y): v for y, v in yearly.items()})
    store.put_meta(
        "energy_imbalance",
        source="Indicators of Global Climate Change, Earth heat inventory",
        source_url="https://github.com/ClimateIndicator/data",
        latest_data=str(max(yearly)),
        status="ok",
    )
    log.info("heat inventory ingested: %d to %d", min(yearly), max(yearly))
    return {"years": len(yearly), "latest": max(yearly)}
