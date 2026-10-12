"""Monsoon stress scoring: rainfall anomaly against the 1991-2020 normal, combined with agent findings.

Regions and their subregions are scored the same way; a subregion uses its own
rainfall box and only the findings the agent tied to it.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from . import food
from .ingest.climateserv import BASELINE, HISTORY_START
from .regions import (
    OFF_SEASON_MONTHS,
    REGIONS,
    Region,
    Season,
    Subregion,
    current_season,
    last_completed_season,
    region_food_mt,
    season_starting,
    subregions_of,
)
from .store import Store

# Findings older than this no longer colour an active region.
AGENT_LOOKBACK_DAYS = 45

LEVELS = ("unknown", "normal", "moderate", "severe")


def rain_level(anomaly_pct: float | None) -> str:
    """Green within 10% of normal (or wetter), yellow 10-25% below, red more than 25% below."""
    if anomaly_pct is None:
        return "unknown"
    if anomaly_pct < -25:
        return "severe"
    if anomaly_pct < -10:
        return "moderate"
    return "normal"


def agent_level(severity: int | None) -> str:
    """Yellow for severity 4-6, red for 7-10."""
    if severity is None:
        return "unknown"
    if severity >= 7:
        return "severe"
    if severity >= 4:
        return "moderate"
    return "normal"


def composite_level(anomaly_pct: float | None, severity: int | None) -> str:
    """The worse of the two signals; unknown only when neither is available."""
    return max(rain_level(anomaly_pct), agent_level(severity), key=LEVELS.index)


def climatology(rows: dict[str, dict]) -> dict[int, float]:
    """Mean monthly rainfall (mm) over the baseline years, from complete months only."""
    totals: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for key, row in rows.items():
        year, month = int(key[:4]), int(key[5:])
        if BASELINE[0] <= year <= BASELINE[1] and row.get("complete"):
            totals[month].append(row["total_mm"])
    return {m: sum(v) / len(v) for m, v in totals.items() if v}


def season_stats(rows: dict[str, dict], normals: dict[int, float], season: Season) -> dict[str, Any]:
    """Observed rainfall over the season's months that have data, against the normal for
    exactly those days. A month observed in part is compared with a pro-rated normal."""
    observed = normal = 0.0
    months_with_data = 0
    through: date | None = None
    for (year, month), key in zip(season.months, season.keys):
        row = rows.get(key)
        if row is None or month not in normals:
            continue
        days_in_month = calendar.monthrange(year, month)[1]
        observed += row["total_mm"]
        normal += normals[month] * row["days"] / days_in_month
        months_with_data += 1
        through = date(year, month, min(row["days"], days_in_month))
    anomaly = (observed / normal - 1) * 100 if normal > 0 else None
    return {
        "season": season.label,
        "start": season.start.isoformat(),
        "end": season.end.isoformat(),
        "observed_mm": round(observed, 1) if months_with_data else None,
        "normal_mm": round(normal, 1) if months_with_data else None,
        "anomaly_pct": round(anomaly, 1) if anomaly is not None else None,
        "months_with_data": months_with_data,
        "months_in_season": len(season.months),
        "data_through": through.isoformat() if through else None,
        "complete": months_with_data == len(season.months)
        and all(rows[k].get("complete") for k in season.keys),
    }


def season_history(region: Region | Subregion, rows: dict[str, dict], normals: dict[int, float], today: date) -> list[dict]:
    """Anomaly of every fully observed past season, oldest first."""
    out = []
    for start_year in range(HISTORY_START, today.year + 1):
        season = season_starting(region, start_year)
        if season.end >= today:
            break
        stats = season_stats(rows, normals, season)
        if stats["complete"]:
            out.append({"season": stats["season"], "start_year": start_year, "anomaly_pct": stats["anomaly_pct"]})
    return out


def _findings(store: Store, region: Region, since: date) -> list[dict]:
    """A region's findings from `since` onwards, newest first."""
    items = store.query(f"FINDING#{region.id}", sk_from=since.isoformat())
    fields = ("date", "date_basis", "category", "kind", "severity", "summary", "evidence_quote",
              "source_url", "source_org", "source_title", "extracted_at", "subregion")
    return sorted(({k: i.get(k) for k in fields} for i in items), key=lambda f: f["date"], reverse=True)


def _observed_severity(findings: list[dict]) -> int | None:
    """Worst severity among reported conditions. Forecasts are shown but never scored."""
    return max((f["severity"] for f in findings if f.get("kind") != "forecast"), default=None)


def _report(store: Store, area: Region | Subregion, today: date, findings: list[dict]) -> dict[str, Any]:
    """Season status, rainfall and score for one box. `findings` are the ones that count
    towards it, reaching back to the start of its last completed season."""
    rows = {i["sk"]: i for i in store.query(f"RAIN#{area.id}")}
    normals = climatology(rows)
    active = current_season(area, today)
    last = last_completed_season(area, today)

    current = season_stats(rows, normals, active) if active else None
    last_stats = season_stats(rows, normals, last)

    # Findings count towards the season they were reported in.
    last_until = (last.end + timedelta(days=AGENT_LOOKBACK_DAYS)).isoformat()
    last_findings = [f for f in findings if last.start.isoformat() <= f["date"] <= last_until]
    recent_from = (today - timedelta(days=AGENT_LOOKBACK_DAYS)).isoformat()
    recent = [f for f in findings if f["date"] >= recent_from]
    recent_severity = _observed_severity(recent)

    if active:
        level = composite_level(current["anomaly_pct"], recent_severity)
    else:
        level = "off_season"

    last_severity = _observed_severity(last_findings)
    return {
        "id": area.id,
        "name": area.name,
        "season_months": list(area.months),
        "geometry": area.polygon,
        "active": active is not None,
        "level": level,
        "rain_level": rain_level(current["anomaly_pct"]) if current else None,
        "agent_level": agent_level(recent_severity) if active else None,
        "agent_severity": recent_severity,
        "current_season": current,
        "last_season": {
            **last_stats,
            "level": composite_level(last_stats["anomaly_pct"], last_severity),
            "agent_severity": last_severity,
            "findings_count": len(last_findings),
        },
        "findings": recent if active else last_findings,
        "history": season_history(area, rows, normals, today),
        "normals_mm": {str(m): round(v, 1) for m, v in sorted(normals.items())},
        "recent_months": [
            {
                "month": key,
                "total_mm": round(row["total_mm"], 1),
                "normal_mm": round(normals[int(key[5:])] * row["days"] / calendar.monthrange(int(key[:4]), int(key[5:]))[1], 1)
                if int(key[5:]) in normals else None,
                "complete": bool(row.get("complete")),
            }
            for key, row in sorted(rows.items())[-18:]
        ],
    }


def _region_findings(store: Store, region: Region, today: date) -> list[dict]:
    return _findings(store, region, last_completed_season(region, today).start)


def region_report(store: Store, region: Region, today: date, findings: list[dict] | None = None) -> dict[str, Any]:
    findings = _region_findings(store, region, today) if findings is None else findings
    subregions = subregions_of(region.id)
    return {
        **_report(store, region, today, findings),
        "hemisphere": region.hemisphere,
        "food_mt": region_food_mt(region.id),
        "subregion_count": len(subregions),
    }


def subregion_report(store: Store, subregion: Subregion, today: date, findings: list[dict] | None = None) -> dict[str, Any]:
    """`findings` are the parent region's; only those the agent tied to this subregion count."""
    region = REGIONS[subregion.region]
    findings = _region_findings(store, region, today) if findings is None else findings
    total = region_food_mt(region.id)
    return {
        **_report(store, subregion, today, [f for f in findings if f.get("subregion") == subregion.id]),
        "region": region.id,
        "region_name": region.name,
        "food_mt": subregion.food_mt,
        "food_share_pct": round(subregion.food_mt / total * 100, 1) if total else None,
        "food_basis": food.basis(subregion.parts),
    }


def region_detail(store: Store, region: Region, today: date) -> dict[str, Any]:
    """A region with every subregion scored the same way, largest producer first."""
    findings = _region_findings(store, region, today)
    subregions = [subregion_report(store, s, today, findings) for s in subregions_of(region.id)]
    return {
        **region_report(store, region, today, findings),
        "subregions": sorted(subregions, key=lambda s: s["food_mt"], reverse=True),
    }


def overview(store: Store, today: date) -> dict[str, Any]:
    regions = [region_report(store, r, today) for r in REGIONS.values()]
    any_active = any(r["active"] for r in regions)
    return {
        "as_of": today.isoformat(),
        "mode": "off_season" if today.month in OFF_SEASON_MONTHS or not any_active else "active",
        "active_regions": [r["id"] for r in regions if r["active"]],
        "baseline": f"{BASELINE[0]}–{BASELINE[1]}",
        "food_unit": "million tonnes of cereals a year",
        "regions": regions,
    }
