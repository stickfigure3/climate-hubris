"""Earth's energy imbalance, from the rate at which the planet is accumulating heat."""

from __future__ import annotations

from typing import Any

from .store import Store

EARTH_SURFACE_M2 = 5.101e14
SECONDS_PER_YEAR = 365.25 * 86400
# One zettajoule a year, spread over the whole surface of the Earth.
W_M2_PER_ZJ_YEAR = 1e21 / (EARTH_SURFACE_M2 * SECONDS_PER_YEAR)

# Single years of heat content are noisy; the imbalance is the mean over this many years.
WINDOW_YEARS = 5
# The ocean's share of the total is measured over this many years of overlap.
SHARE_YEARS = 15


def total_heat(rows: dict[int, dict[str, float | None]]) -> dict[int, float]:
    """Heat inventory in ZJ for every year.

    The source publishes land, ice and atmosphere a few years behind the ocean. Those
    years are filled by assuming the ocean kept taking the share of the heat it took
    over the last SHARE_YEARS years that have all components (about 91%).
    """
    total = {y: r["total"] for y, r in rows.items() if r["total"] is not None}
    if not total:
        return {}
    last = max(total)
    first = max(min(total), last - SHARE_YEARS)
    gained = total[last] - total[first]
    share = (rows[last]["ocean"] - rows[first]["ocean"]) / gained if gained else 1.0
    for year, row in rows.items():
        if year > last and share > 0:
            total[year] = total[last] + (row["ocean"] - rows[last]["ocean"]) / share
    return total


def imbalance(heat: dict[int, float], window: int = WINDOW_YEARS) -> dict[int, float]:
    """W/m² averaged over the `window` years ending in each year."""
    return {
        year: (heat[year] - heat[year - window]) / window * W_M2_PER_ZJ_YEAR
        for year in sorted(heat)
        if year - window in heat
    }


def load(store: Store) -> dict[int, dict[str, float | None]]:
    return {int(i["sk"]): {"ocean": i["ocean"], "total": i.get("total")} for i in store.query("HEAT_INVENTORY")}


def summary(store: Store) -> dict[str, Any]:
    rows = load(store)
    measured = [y for y, r in rows.items() if r["total"] is not None]
    series = imbalance(total_heat(rows))
    return {
        "unit": "W/m^2",
        "window_years": WINDOW_YEARS,
        # Years after this one rest on ocean heat alone.
        "all_components_through": max(measured) if measured else None,
        "series": [{"year": y, "value": round(v, 3)} for y, v in series.items()],
    }
