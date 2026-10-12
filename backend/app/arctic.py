"""Assembles the Arctic module's API payloads from stored PIOMAS and OHC data."""

from __future__ import annotations

from typing import Any

from . import boe
from .ingest.piomas import day_to_date
from .store import Store

COMPARISON_YEAR = 2000
OHC_LAYERS = {"700": "OHC_700", "2000": "OHC_2000"}


def load_monthly(store: Store) -> dict[int, list[float | None]]:
    return {int(i["sk"]): i["values"] for i in store.query("PIOMAS_MONTHLY")}


def load_ohc(store: Store, layer: str) -> dict[int, float]:
    return {int(i["sk"]): i["value"] for i in store.query(OHC_LAYERS[layer])}


def comparison(store: Store) -> dict[str, Any] | None:
    """Volume on the latest published day against the same calendar day in 2000."""
    daily = {int(i["sk"]): i["values"] for i in store.query("PIOMAS_DAILY")}
    if not daily or COMPARISON_YEAR not in daily:
        return None
    year = max(daily)
    day = len(daily[year])
    now, then = daily[year][day - 1], daily[COMPARISON_YEAR][day - 1]
    return {
        "date": day_to_date(year, day).isoformat(),
        "volume": now,
        "reference_date": day_to_date(COMPARISON_YEAR, day).isoformat(),
        "reference_volume": then,
        "difference": now - then,
        "percent_change": (now / then - 1) * 100,
        "unit": "10^3 km^3",
    }


def projection(
    store: Store, baseline_year: int = 2000, rate_window: int = 10, layer: str = "700", threshold: float = 0.0
) -> dict[str, Any]:
    minima = boe.annual_minima(load_monthly(store))
    result = boe.project_boe(minima, load_ohc(store, layer), baseline_year, rate_window, threshold)
    result["inputs"]["layer"] = layer
    result["trend"] = boe.trend_projection(minima, threshold)
    return result


def summary(store: Store) -> dict[str, Any]:
    monthly = load_monthly(store)
    minima = boe.annual_minima(monthly)
    ohc = {layer: load_ohc(store, layer) for layer in OHC_LAYERS}
    return {
        "comparison": comparison(store),
        "monthly": [
            {"year": y, "month": m + 1, "volume": v}
            for y, values in sorted(monthly.items())
            for m, v in enumerate(values)
            if v is not None
        ],
        "annual_minima": [{"year": y, "volume": v} for y, v in sorted(minima.items())],
        "ohc": {
            layer: [{"year": y, "value": v} for y, v in sorted(series.items())]
            for layer, series in ohc.items()
        },
        "projection": projection(store),
        "controls": {
            "baseline_years": {
                layer: [y for y in sorted(set(minima) & set(series)) if y < max(set(minima) & set(series))]
                for layer, series in ohc.items()
            },
            "rate_window": {"min": 3, "max": 20, "default": 10},
            "threshold": {"min": 0, "max": 2, "default": 0},
        },
    }
