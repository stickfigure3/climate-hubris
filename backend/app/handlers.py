"""Lambda entry points for the scheduled jobs (EventBridge -> Lambda)."""

from __future__ import annotations

import logging

from .agent import run as agent
from .ingest import climateserv, eei, imd, ohc, piomas
from .store import Store

logging.getLogger().setLevel(logging.INFO)
log = logging.getLogger(__name__)


def ingest_arctic(event, context) -> dict:
    """Twice a month: PIOMAS sea ice volume, NOAA ocean heat content and Earth's heat inventory."""
    store = Store()
    return {"piomas": piomas.ingest(store), "ohc": ohc.ingest(store), "energy_imbalance": eei.ingest(store)}


def ingest_monsoon(event, context) -> dict:
    """Weekly: rainfall for every region and subregion, plus IMD state data when reachable."""
    store = Store()
    return {
        "rainfall": climateserv.ingest(
            store, seconds_left=lambda: context.get_remaining_time_in_millis() / 1000
        ),
        "imd": imd.ingest(store),
    }


def run_agent(event, context) -> dict:
    """Weekly trigger; the agent itself drops to twice a month outside monsoon seasons."""
    store = Store()
    try:
        return agent.run(store, force=bool((event or {}).get("force")))
    except Exception:
        log.exception("agent run failed")
        store.put_meta("agent", status="error", detail="Last run raised an exception; see logs.")
        raise
