"""Monsoon stress scoring: rainfall anomaly against the 1991-2020 normal, combined with agent findings."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Any

from .ingest.climateserv import BASELINE, HISTORY_START
from .regions import (
    OFF_SEASON_MONTHS,
    REGIONS,
    Region,
    Season,
    current_season,
    last_completed_season,
    season_starting,
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


def season_history(region: Region, rows: dict[str, dict], normals: dict[int, float], today: date) -> list[dict]:
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
    items = store.query(f"FINDING#{region.id}", sk_from=since.isoformat())
    fields = ("date", "date_basis", "category", "kind", "severity", "summary", "evidence_quote",
              "source_url", "source_org", "source_title", "extracted_at")
    return sorted(({k: i.get(k) for k in fields} for i in items), key=lambda f: f["date"], reverse=True)


def _observed_severity(findings: list[dict]) -> int | None:
    """Worst severity among reported conditions. Forecasts are shown but never scored."""
    return max((f["severity"] for f in findings if f.get("kind") != "forecast"), default=None)


def region_report(store: Store, region: Region, today: date) -> dict[str, Any]:
    rows = {i["sk"]: i for i in store.query(f"RAIN#{region.id}")}
    normals = climatology(rows)
    active = current_season(region, today)
    last = last_completed_season(region, today)

    current = season_stats(rows, normals, active) if active else None
    last_stats = season_stats(rows, normals, last)

    # Findings count towards the season they were reported in.
    last_findings = [
        f for f in _findings(store, region, last.start)
        if f["date"] <= (last.end + timedelta(days=AGENT_LOOKBACK_DAYS)).isoformat()
    ]
    recent = _findings(store, region, today - timedelta(days=AGENT_LOOKBACK_DAYS))
    recent_severity = _observed_severity(recent)

    if active:
        level = composite_level(current["anomaly_pct"], recent_severity)
    else:
        level = "off_season"

    last_severity = _observed_severity(last_findings)
    return {
        "id": region.id,
        "name": region.name,
        "hemisphere": region.hemisphere,
        "season_months": list(region.months),
        "geometry": region.polygon,
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
        "history": season_history(region, rows, normals, today),
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


def overview(store: Store, today: date) -> dict[str, Any]:
    regions = [region_report(store, r, today) for r in REGIONS.values()]
    any_active = any(r["active"] for r in regions)
    return {
        "as_of": today.isoformat(),
        "mode": "off_season" if today.month in OFF_SEASON_MONTHS or not any_active else "active",
        "active_regions": [r["id"] for r in regions if r["active"]],
        "baseline": f"{BASELINE[0]}–{BASELINE[1]}",
        "regions": regions,
    }
