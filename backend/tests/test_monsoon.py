from datetime import date

import pytest

from app import monsoon
from app.agent.run import should_run
from app.regions import REGIONS, current_season, last_completed_season, season_starting


@pytest.mark.parametrize(
    "anomaly, level",
    [(None, "unknown"), (12.0, "normal"), (-10.0, "normal"), (-10.1, "moderate"),
     (-25.0, "moderate"), (-25.1, "severe")],
)
def test_rain_level_thresholds(anomaly, level):
    assert monsoon.rain_level(anomaly) == level


@pytest.mark.parametrize("severity, level", [(None, "unknown"), (3, "normal"), (4, "moderate"), (6, "moderate"), (7, "severe")])
def test_agent_level_thresholds(severity, level):
    assert monsoon.agent_level(severity) == level


def test_composite_takes_the_worse_signal():
    assert monsoon.composite_level(-5.0, 8) == "severe"
    assert monsoon.composite_level(-30.0, 2) == "severe"
    assert monsoon.composite_level(None, 5) == "moderate"
    assert monsoon.composite_level(None, None) == "unknown"


def test_seasons_that_cross_new_year():
    australia = REGIONS["australia"]
    season = season_starting(australia, 2025)
    assert season.keys == ["2025-12", "2026-01", "2026-02", "2026-03"]
    assert season.label == "2025–26"
    assert current_season(australia, date(2026, 1, 15)).start_year == 2025
    assert current_season(australia, date(2026, 10, 10)) is None
    assert last_completed_season(australia, date(2026, 10, 10)).start_year == 2025


def test_south_asia_season_boundaries():
    india = REGIONS["south_asia"]
    assert current_season(india, date(2026, 6, 1)).label == "2026"
    assert current_season(india, date(2026, 9, 30)) is not None
    assert current_season(india, date(2026, 10, 1)) is None
    assert last_completed_season(india, date(2026, 10, 10)).label == "2026"
    assert last_completed_season(india, date(2026, 7, 1)).label == "2025"


def _rows(per_month_mm: dict[str, float]) -> dict:
    return {k: {"total_mm": v, "days": 30, "complete": True} for k, v in per_month_mm.items()}


def test_season_stats_compares_only_months_with_data():
    india = REGIONS["south_asia"]
    normals = {6: 160.0, 7: 290.0, 8: 260.0, 9: 170.0}
    rows = _rows({"2026-06": 120.0, "2026-07": 290.0})
    rows["2026-08"] = {"total_mm": 65.0, "days": 15, "complete": False}  # half of August observed
    stats = monsoon.season_stats(rows, normals, season_starting(india, 2026))

    normal_to_date = 160.0 * 30 / 30 + 290.0 * 30 / 31 + 260.0 * 15 / 31
    assert stats["observed_mm"] == 475.0
    assert stats["normal_mm"] == pytest.approx(normal_to_date, abs=0.1)
    assert stats["anomaly_pct"] == pytest.approx((475.0 / normal_to_date - 1) * 100, abs=0.1)
    assert stats["months_with_data"] == 3
    assert stats["data_through"] == "2026-08-15"
    assert not stats["complete"]


def test_agent_runs_weekly_in_season_and_twice_a_month_otherwise():
    assert should_run(date(2026, 7, 27))  # South Asian monsoon active
    assert should_run(date(2026, 1, 26))  # southern-hemisphere monsoons active
    # April and October: no monsoon is active.
    assert [d for d in (5, 12, 19, 26) if should_run(date(2026, 10, d))] == [5, 19]
    assert [d for d in (6, 13, 20, 27) if should_run(date(2026, 4, d))] == [6, 20]
