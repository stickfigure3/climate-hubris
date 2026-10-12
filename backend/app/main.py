"""FastAPI application. Runs under uvicorn locally and under Mangum on Lambda."""

from __future__ import annotations

import csv
import io
import time
from datetime import datetime, timezone
from typing import Any, Callable, Literal

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from . import arctic, boe, energy, food, monsoon
from .config import settings
from .regions import AREAS, REGIONS, SUBREGIONS
from .store import Store

app = FastAPI(
    title="Climate Hubris API",
    description="Arctic sea ice volume, a first-order Blue Ocean Event projection, and global monsoon stress.",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)

_store: Store | None = None
_cache: dict[str, tuple[float, Any]] = {}
CACHE_SECONDS = 300  # source data changes weekly at most
CACHE_MAX_ENTRIES = 500  # projection parameters are caller-chosen; do not let them grow the cache forever


def store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


def cached(key: str, build: Callable[[], Any]) -> Any:
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_SECONDS:
        return hit[1]
    value = build()
    if len(_cache) >= CACHE_MAX_ENTRIES:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)
    return value


def _today():
    return datetime.now(timezone.utc).date()


@app.middleware("http")
async def cache_headers(request, call_next):
    response = await call_next(request)
    if request.method == "GET" and response.status_code == 200:
        response.headers.setdefault("Cache-Control", "public, max-age=300")
    return response


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/meta")
def meta() -> dict:
    """When each dataset was last ingested and how recent its newest value is."""
    return cached("meta", lambda: {"datasets": store().get_meta(), "server_time": datetime.now(timezone.utc).isoformat()})


@app.get("/api/arctic")
def arctic_summary() -> dict:
    data = cached("arctic", lambda: arctic.summary(store()))
    if not data["monthly"]:
        raise HTTPException(503, "Sea ice data has not been ingested yet.")
    return data


@app.get("/api/arctic/projection")
def arctic_projection(
    baseline_year: int | None = Query(None, ge=1979, le=2100, description="Defaults to the oldest year on record."),
    rate_window: int | None = Query(
        None, ge=boe.RATE_WINDOW_MIN, le=boe.RATE_WINDOW_MAX, description="Defaults to the years since 2020."
    ),
    layer: Literal["700", "2000"] = "700",
    threshold: float = Query(0.0, ge=0, le=2, description="Volume counted as ice-free, in 10^3 km^3."),
) -> dict:
    threshold = round(threshold, 2)
    key = f"projection:{baseline_year}:{rate_window}:{layer}:{threshold}"
    return cached(key, lambda: arctic.projection(store(), baseline_year, rate_window, layer, threshold))


@app.get("/api/monsoon")
def monsoon_overview() -> dict:
    today = _today()
    return cached(f"monsoon:{today}", lambda: monsoon.overview(store(), today))


@app.get("/api/monsoon/{area_id}")
def monsoon_area(area_id: str) -> dict:
    """A region with its subregions, or one subregion by its "<region>.<subregion>" id."""
    today = _today()
    if area_id in REGIONS:
        return cached(f"monsoon:{today}:{area_id}", lambda: monsoon.region_detail(store(), REGIONS[area_id], today))
    if area_id in SUBREGIONS:
        return cached(
            f"monsoon:{today}:{area_id}", lambda: monsoon.subregion_report(store(), SUBREGIONS[area_id], today)
        )
    raise HTTPException(
        404, f"Unknown region. Choose one of: {', '.join(REGIONS)}, or a subregion id such as south_asia.pakistan"
    )


def _csv(filename: str, header: list[str], rows: list[list[Any]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/arctic.csv")
def export_arctic() -> Response:
    """Monthly PIOMAS volume, with the annual minimum, ocean heat content and energy imbalance repeated per year."""
    s = store()
    monthly = arctic.load_monthly(s)
    minima = boe.annual_minima(monthly)
    ohc700, ohc2000 = arctic.load_ohc(s, "700"), arctic.load_ohc(s, "2000")
    imbalance = {p["year"]: p["value"] for p in energy.summary(s)["series"]}
    rows = [
        [y, m + 1, v, minima.get(y, ""), ohc700.get(y, ""), ohc2000.get(y, ""), imbalance.get(y, "")]
        for y, values in sorted(monthly.items())
        for m, v in enumerate(values)
        if v is not None
    ]
    header = ["year", "month", "ice_volume_1000km3", "annual_min_volume_1000km3", "ohc_0_700m_zj", "ohc_0_2000m_zj",
              "energy_imbalance_w_m2_5yr_mean"]
    return _csv("climate-hubris-arctic.csv", header, rows)


@app.get("/api/export/monsoon.csv")
def export_monsoon() -> Response:
    """Monthly rainfall for every region and subregion with its 1991-2020 normal."""
    s = store()
    rows = []
    for region in AREAS.values():
        stored = {i["sk"]: i for i in s.query(f"RAIN#{region.id}")}
        normals = monsoon.climatology(stored)
        for key, row in sorted(stored.items()):
            normal = normals.get(int(key[5:]))
            anomaly = round((row["total_mm"] / normal - 1) * 100, 1) if normal and row.get("complete") else ""
            rows.append([region.id, key, round(row["total_mm"], 2), round(normal, 2) if normal else "",
                         anomaly, row["days"], int(key[5:]) in region.months])
    header = ["region", "month", "rainfall_mm", "normal_mm_1991_2020", "anomaly_pct", "days_observed", "in_monsoon_season"]
    return _csv("climate-hubris-monsoon-rainfall.csv", header, rows)


@app.get("/api/export/findings.csv")
def export_findings() -> Response:
    s = store()
    fields = ["region", "subregion", "date", "date_basis", "category", "kind", "severity", "summary", "evidence_quote",
              "source_org", "source_url", "extracted_at", "model"]
    rows = [[item.get(f, "") for f in fields] for region in REGIONS for item in s.query(f"FINDING#{region}")]
    return _csv("climate-hubris-monsoon-findings.csv", fields, rows)


@app.get("/api/export/food.csv")
def export_food() -> Response:
    """The cereal production estimate behind each box on the map."""
    rows = [
        [sub.region, sub.id, sub.name, sub.food_mt, *sub.bbox, food.basis(sub.parts)]
        for sub in SUBREGIONS.values()
    ]
    header = ["region", "subregion", "name", "cereals_million_tonnes_per_year", "west", "south", "east", "north", "basis"]
    return _csv("climate-hubris-food-production.csv", header, rows)


handler = Mangum(app, lifespan="off")
