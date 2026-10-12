from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def client(store, monkeypatch):
    monkeypatch.setattr(main, "_store", store)
    monkeypatch.setattr(main, "_cache", {})
    monkeypatch.setattr(main, "_today", lambda: date(2026, 10, 10))

    # Ice: a steady decline with a September minimum; OHC: a steady rise.
    for year in range(1995, 2026):
        september = 12.0 - 0.3 * (year - 1995)
        store.put("PIOMAS_MONTHLY", str(year), values=[september + 15] * 8 + [september] + [september + 2] * 3)
        store.put("PIOMAS_DAILY", str(year), values=[30.0 - 0.3 * (year - 1995)] * 365)
        store.put("OHC_700", str(year), value=20.0 + 7.0 * (year - 1995), se=1.0)
    store.put("PIOMAS_MONTHLY", "2026", values=[20.0, 22.0] + [None] * 10)
    store.put("PIOMAS_DAILY", "2026", values=[20.0] * 59)

    # Rainfall: every month at 100 mm, except a dry 2026 South Asian monsoon.
    for region in ("south_asia", "australia"):
        store.put_many(
            f"RAIN#{region}",
            {f"{y}-{m:02d}": {"total_mm": 100.0, "days": 30, "complete": True}
             for y in range(1991, 2027) for m in range(1, 13) if (y, m) <= (2026, 8)},
        )
    for month in ("2026-06", "2026-07", "2026-08"):
        store.put("RAIN#south_asia", month, total_mm=60.0, days=30, complete=True)
    store.put("FINDING#south_asia", "2026-08-20#abc", region="south_asia", date="2026-08-20",
              date_basis="published", category="drought", kind="observed", severity=7, summary="Drought declared.",
              evidence_quote="drought was declared", source_url="https://example.org/a",
              source_org="FAO GIEWS", source_title="Brief", extracted_at="2026-08-21T00:00:00Z")
    store.put("FINDING#south_asia", "2026-09-01#def", region="south_asia", date="2026-09-01",
              date_basis="published", category="flooding", kind="forecast", severity=9, summary="Floods expected.",
              evidence_quote="floods are expected", source_url="https://example.org/b",
              source_org="FEWS NET", source_title="Outlook", extracted_at="2026-09-02T00:00:00Z")
    store.put_meta("piomas_daily", latest_data="2026-02-28", status="ok")
    return TestClient(main.app)


def test_arctic_summary(client):
    body = client.get("/api/arctic").json()
    comparison = body["comparison"]
    assert comparison["date"] == "2026-02-28"
    assert comparison["reference_date"] == "2000-02-28"
    assert comparison["volume"] == 20.0
    assert comparison["reference_volume"] == pytest.approx(28.5)
    assert comparison["percent_change"] == pytest.approx((20 / 28.5 - 1) * 100)
    assert body["annual_minima"][-1] == {"year": 2025, "volume": pytest.approx(3.0)}
    assert body["projection"]["valid"]
    # 3.0 left, losing 0.3 a year.
    assert body["projection"]["boe_year"] == pytest.approx(2035.0)
    assert body["projection"]["trend"]["zero_year"] == pytest.approx(2035.0)


def test_projection_parameters(client):
    r = client.get("/api/arctic/projection", params={"baseline_year": 2005, "rate_window": 5, "threshold": 1})
    body = r.json()
    assert body["valid"] and body["inputs"]["baseline_year"] == 2005
    assert body["boe_year"] == pytest.approx(2025 + 2.0 / 0.3)
    assert client.get("/api/arctic/projection", params={"rate_window": 50}).status_code == 422
    missing = client.get("/api/arctic/projection", params={"layer": "2000"}).json()
    assert not missing["valid"] and "reason" in missing


def test_monsoon_overview_in_october(client):
    body = client.get("/api/monsoon").json()
    assert body["mode"] == "off_season"
    india = next(r for r in body["regions"] if r["id"] == "south_asia")
    assert india["level"] == "off_season" and not india["active"]
    last = india["last_season"]
    assert last["season"] == "2026"
    assert last["anomaly_pct"] == pytest.approx(-40.0, abs=2.5)  # 31-day months shift the normal slightly
    assert last["months_with_data"] == 3 and not last["complete"]
    assert last["level"] == "severe"
    assert last["findings_count"] == 2
    assert last["agent_severity"] == 7  # the severity-9 forecast is listed but not scored
    assert [f["kind"] for f in india["findings"]] == ["forecast", "observed"]
    assert india["history"][-1]["season"] == "2025"


def test_region_endpoint_and_unknown_region(client):
    assert client.get("/api/monsoon/australia").json()["last_season"]["season"] == "2025–26"
    assert client.get("/api/monsoon/atlantis").status_code == 404


def test_exports_are_csv(client):
    arctic = client.get("/api/export/arctic.csv")
    assert arctic.headers["content-type"].startswith("text/csv")
    assert arctic.text.splitlines()[0].startswith("year,month,ice_volume_1000km3")
    rainfall = client.get("/api/export/monsoon.csv").text.splitlines()
    assert rainfall[0].startswith("region,month,rainfall_mm")
    findings = client.get("/api/export/findings.csv").text
    assert "Drought declared." in findings


def test_meta_reports_freshness(client):
    assert client.get("/api/meta").json()["datasets"]["piomas_daily"]["latest_data"] == "2026-02-28"
