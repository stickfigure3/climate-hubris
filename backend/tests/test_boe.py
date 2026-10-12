import pytest

from app import boe


def test_annual_minima_skips_years_without_a_september():
    monthly = {
        2024: [16, 19, 21, 22, 21, 17, 10, 5.3, 4.2, 5.2, 8, 11.8],
        2026: [14.7, 17.7] + [None] * 10,
    }
    assert boe.annual_minima(monthly) == {2024: 4.2}


def test_projection_matches_the_formula_by_hand():
    minima = {2000: 11.0, 2015: 6.0, 2025: 4.0}
    ohc = {2000: 60.0, 2015: 155.0, 2025: 228.0}
    r = boe.project_boe(minima, ohc, baseline_year=2000, rate_window=10)

    sensitivity = (4.0 - 11.0) / (228.0 - 60.0)  # 10^3 km^3 per ZJ
    rate = (228.0 - 155.0) / 10  # ZJ per year
    years = 4.0 / (-sensitivity * rate)
    assert r["valid"]
    assert r["sensitivity_km3_per_zj"] == pytest.approx(sensitivity * 1000)
    assert r["ohc_rate_zj_per_year"] == pytest.approx(rate)
    assert r["years_to_boe"] == pytest.approx(years)
    assert r["boe_year"] == pytest.approx(2025 + years)
    assert r["path"][0] == {"year": 2025, "volume": 4.0}
    assert r["path"][-1]["volume"] == 0.0


def test_a_higher_threshold_brings_the_date_forward():
    minima = {2000: 11.0, 2015: 6.0, 2025: 4.0}
    ohc = {2000: 60.0, 2015: 155.0, 2025: 228.0}
    zero = boe.project_boe(minima, ohc)["boe_year"]
    one = boe.project_boe(minima, ohc, threshold=1.0)["boe_year"]
    assert one < zero


@pytest.mark.parametrize(
    "minima, ohc, kwargs, reason",
    [
        ({2000: 11.0, 2025: 4.0}, {2000: 60.0, 2025: 228.0}, {"baseline_year": 1990}, "baseline"),
        ({2000: 11.0, 2025: 4.0}, {2000: 60.0, 2025: 228.0}, {}, "2015"),  # rate window start missing
        ({2000: 4.0, 2015: 5.0, 2025: 6.0}, {2000: 60.0, 2015: 155.0, 2025: 228.0}, {}, "sensitivity"),
        ({}, {}, {}, "No year"),
    ],
)
def test_projection_reports_why_it_cannot_run(minima, ohc, kwargs, reason):
    r = boe.project_boe(minima, ohc, **kwargs)
    assert not r["valid"]
    assert reason in r["reason"]


def test_trend_projection_zero_crossing():
    t = boe.trend_projection({2000: 10.0, 2010: 8.0, 2020: 6.0})
    assert t["slope_km3_per_year"] == pytest.approx(-200)
    assert t["zero_year"] == pytest.approx(2050)
