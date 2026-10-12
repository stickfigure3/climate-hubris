"""India Meteorological Department state-wise rainfall.

IMD only answers allow-listed IP addresses (it replies 401 "Your IP ... needs to
be whitelisted" otherwise), and Lambda has no fixed egress IP without a NAT
gateway. Until an address is allow-listed this source records itself as
unavailable and the South Asian region falls back to CHIRPS alone.

The response schema below could not be verified against a live response for the
same reason: rows are stored as received, and the departure field is located by
name rather than assumed.
"""

from __future__ import annotations

import logging
import re

import httpx

from ..config import settings
from ..store import Store

log = logging.getLogger(__name__)

STATE_URL = "https://mausam.imd.gov.in/api/statewise_rainfall_api.php"


def _departure(row: dict) -> float | None:
    for key, value in row.items():
        if "dep" in key.lower():
            try:
                return float(str(value).replace("%", "").strip())
            except ValueError:
                return None
    return None


def ingest(store: Store, client: httpx.Client | None = None) -> dict:
    client = client or httpx.Client(headers={"User-Agent": settings.user_agent}, timeout=30)
    try:
        response = client.get(STATE_URL)
    except httpx.HTTPError as exc:
        detail = f"Request failed: {exc.__class__.__name__}"
        store.put_meta("imd_statewise", source_url=STATE_URL, status="unavailable", detail=detail)
        return {"status": "unavailable", "detail": detail}

    rows = None
    if response.status_code == 200:
        try:
            body = response.json()
            rows = body if isinstance(body, list) else None
        except ValueError:
            rows = None
    if not rows:
        # The refusal message echoes our IP address; keep that out of the public freshness record.
        message = re.sub(r"\d{1,3}(\.\d{1,3}){3}", "<address>", response.text.strip()[:200])
        detail = f"HTTP {response.status_code}: {message}" if message else f"HTTP {response.status_code}"
        log.warning("IMD unavailable: %s", detail)
        store.put_meta("imd_statewise", source_url=STATE_URL, status="unavailable", detail=detail)
        return {"status": "unavailable", "detail": detail}

    states = [{"raw": row, "departure_pct": _departure(row)} for row in rows if isinstance(row, dict)]
    store.put("IMD", "latest", states=states)
    store.put_meta(
        "imd_statewise",
        source="India Meteorological Department",
        source_url=STATE_URL,
        status="ok",
        detail=f"{len(states)} states",
    )
    return {"status": "ok", "states": len(states)}
