"""Global ocean heat content anomaly (NOAA NCEI, Levitus et al.)."""

from __future__ import annotations

import logging
from datetime import timezone
from email.utils import parsedate_to_datetime

import httpx

from ..config import settings
from ..store import Store

log = logging.getLogger(__name__)

BASE = "https://www.ncei.noaa.gov/data/oceans/woa/DATA_ANALYSIS/3M_HEAT_CONTENT/DATA/basin/yearly"
LAYERS = {
    "OHC_700": f"{BASE}/h22-w0-700m.dat",  # 0-700 m, 1955 onwards
    "OHC_2000": f"{BASE}/h22-w0-2000m.dat",  # 0-2000 m, 2005 onwards
}

# NCEI publishes in units of 10^22 J. 1 ZJ = 10^21 J.
ZJ_PER_UNIT = 10.0


def parse_yearly(text: str) -> dict[int, dict[str, float]]:
    """year -> {value, se} in ZJ, from the world-ocean (WO) columns.

    Rows are stamped mid-year (e.g. 2005.500) and hold the annual mean anomaly.
    """
    out: dict[int, dict[str, float]] = {}
    lines = text.splitlines()
    header = lines[0].split()
    wo, wo_se = header.index("WO"), header.index("WOse")
    for line in lines[1:]:
        parts = line.split()
        if len(parts) <= wo_se:
            continue
        out[int(float(parts[0]))] = {
            "value": float(parts[wo]) * ZJ_PER_UNIT,
            "se": float(parts[wo_se]) * ZJ_PER_UNIT,
        }
    return out


def ingest(store: Store, client: httpx.Client | None = None) -> dict:
    client = client or httpx.Client(
        headers={"User-Agent": settings.user_agent}, timeout=60, follow_redirects=True
    )
    summary = {}
    for dataset, url in LAYERS.items():
        response = client.get(url)
        response.raise_for_status()
        yearly = parse_yearly(response.text)
        store.put_many(dataset, {str(y): v for y, v in yearly.items()})
        modified = response.headers.get("last-modified")
        store.put_meta(
            dataset.lower(),
            source="NOAA NCEI Global Ocean Heat and Salt Content",
            source_url=url,
            source_last_modified=(
                parsedate_to_datetime(modified).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                if modified
                else None
            ),
            latest_data=str(max(yearly)),
            status="ok",
        )
        summary[dataset] = max(yearly)
    log.info("OHC ingested: %s", summary)
    return summary
