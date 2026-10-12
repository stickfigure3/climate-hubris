"""Assembles the Arctic module's API payloads from stored PIOMAS and OHC data."""

from __future__ import annotations

from typing import Any

from . import boe, energy
from .ingest.piomas import day_to_date
from .store import Store

OHC_LAYERS = {"700": "OHC_700", "2000": "OHC_2000"}


def load_monthly(store: Store) -> dict[int, list[float | None]]:
    return {int(i["sk"]): i["values"] for i in store.query("PIOMAS_MONTHLY")}


def load_ohc(store: Store, layer: str) -> dict[int, float]:
    return {int(i["sk"]): i["value"] for i in store.query(OHC_LAYERS[layer])}


def comparison(store: Store) -> dict[str, Any] | None:
    """Volume on the latest published day against the same calendar day in the oldest year on record."""
    daily = {int(i["sk"]): i["values"] for i in store.query("PIOMAS_DAILY")}
    if not daily:
        return None
    year = max(daily)
    day = len(daily[year])
    reference_year = min((y for y, values in daily.items() if len(values) >= day and y < year), default=None)
    if reference_year is None:
        return None
    now, then = daily[year][day - 1], daily[reference_year][day - 1]
    return {
        "date": day_to_date(year, day).isoformat(),
        "volume": now,
        "reference_date": day_to_date(reference_year, day).isoformat(),
        "reference_volume": then,
        "difference": now - then,
        "percent_change": (now / then - 1) * 100,
        "unit": "10^3 km^3",
    }


def projection(
    store: Store,
    baseline_year: int | None = None,
    rate_window: int | None = None,
    layer: str = "700",
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Baseline and rate window default to the oldest shared year and the years since 2020."""
    minima = boe.annual_minima(load_monthly(store))
    result = boe.project_boe(minima, load_ohc(store, layer), baseline_year, rate_window, threshold)
    result["inputs"]["layer"] = layer
    result["trend"] = boe.trend_projection(minima, threshold)
    return result


def summary(store: Store) -> dict[str, Any]:
    monthly = load_monthly(store)
    minima = boe.annual_minima(monthly)
    ohc = {layer: load_ohc(store, layer) for layer in OHC_LAYERS}
    shared = {layer: sorted(set(minima) & set(series)) for layer, series in ohc.items()}
    latest = max((years[-1] for years in shared.values() if years), default=None)
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
        "energy_imbalance": energy.summary(store),
        "projection": projection(store),
        "controls": {
            "baseline_years": {layer: years[:-1] for layer, years in shared.items()},
            "rate_window": {
                "min": boe.RATE_WINDOW_MIN,
                "max": boe.RATE_WINDOW_MAX,
                "default": boe.default_rate_window(latest) if latest else boe.RATE_WINDOW_MAX,
            },
            "threshold": {"min": 0, "max": 2, "default": 0},
        },
    }
