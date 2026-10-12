from datetime import date

import pytest

from app import energy, food
from app.ingest import climateserv, eei, ohc, piomas
from app.regions import REGIONS, SUBREGIONS, region_food_mt, subregions_of

MONTHLY = """year,Jan,Feb,Mar,Apr,May,Jun,Jul,Aug,Sep,Oct,Nov,Dec
2025.00,15.3692,18.1445,20.4186,21.6571,20.3487,15.7402,9.40362,5.14601,4.02091,4.94648,7.72189,11.0970
2026.00,14.6627,17.7057,-1.00000,-1.00000,-1.00000,-1.00000,-1.00000,-1.00000,-1.00000,-1.00000,-1.00000,-1.00000
"""

DAILY = """Year #day Vol
1979   1  26.405
1979   2  26.496
1980   1  25.100
"""

OHC = """    YEAR      WO    WOse      NH    NHse      SH    SHse
2024.500  21.469   0.195  10.174   0.268  11.295   0.421
2025.500  22.845   0.175  11.850   0.239  10.995   0.242
"""


def test_piomas_monthly_marks_unpublished_months_as_missing():
    parsed = piomas.parse_monthly(MONTHLY)
    assert parsed[2025][8] == pytest.approx(4.02091)
    assert parsed[2026][:2] == [14.6627, 17.7057]
    assert parsed[2026][2:] == [None] * 10


def test_piomas_daily_groups_by_year():
    assert piomas.parse_daily(DAILY) == {1979: [26.405, 26.496], 1980: [25.1]}


def test_piomas_daily_rejects_a_gap():
    with pytest.raises(ValueError):
        piomas.parse_daily("Year #day Vol\n1979 1 26.4\n1979 3 26.5\n")


def test_piomas_day_numbers_use_a_365_day_calendar():
    assert piomas.day_to_date(2026, 59) == date(2026, 2, 28)
    assert piomas.day_to_date(2024, 60) == date(2024, 3, 1)  # leap years still skip 29 Feb
    assert piomas.day_to_date(2000, 365) == date(2000, 12, 31)


def test_ohc_is_converted_from_1e22_joules_to_zettajoules():
    parsed = ohc.parse_yearly(OHC)
    assert parsed[2025]["value"] == pytest.approx(228.45)
    assert parsed[2025]["se"] == pytest.approx(1.75)


def test_rainfall_months_know_whether_they_are_complete():
    daily = [(date(2025, 6, d), 2.0) for d in range(1, 31)] + [(date(2025, 7, d), 1.0) for d in range(1, 11)]
    months = climateserv.to_monthly(daily)
    assert months["2025-06"] == {"total_mm": 60.0, "days": 30, "complete": True}
    assert months["2025-07"] == {"total_mm": 10.0, "days": 10, "complete": False}


HEAT = """time,timebound_lower,timebound_upper,atmosphere,ocean_full-depth,ocean_full-depth_error,total
2019.5,2019,2020,4.7,416.8,30.2,457.5
2020.5,2020,2021,5.6,438.3,32.7,481.0
2021.5,2021,2022,,457.5,35.3,
,,,,473.7,36.6,
"""


def test_heat_inventory_keeps_ocean_only_years_and_dates_an_unstamped_row():
    parsed = eei.parse(HEAT)
    assert parsed[2020] == {"ocean": 438.3, "total": 481.0}
    assert parsed[2021] == {"ocean": 457.5, "total": None}
    assert parsed[2022] == {"ocean": 473.7, "total": None}


def test_energy_imbalance_is_the_rate_of_heat_gain_per_square_metre():
    # 16.1 ZJ a year over the whole Earth is 1 W/m².
    assert energy.W_M2_PER_ZJ_YEAR * 16.1 == pytest.approx(1.0, abs=0.001)
    rows = {y: {"ocean": 9.0 * (y - 2000), "total": 10.0 * (y - 2000) if y <= 2020 else None} for y in range(2000, 2026)}
    heat = energy.total_heat(rows)
    assert heat[2025] == pytest.approx(250.0)  # ocean-only years divided by the ocean's 90% share
    series = energy.imbalance(heat, window=5)
    assert min(series) == 2005
    assert series[2025] == pytest.approx(10.0 * energy.W_M2_PER_ZJ_YEAR)


def test_food_estimates_scale_a_country_by_its_states_share():
    whole = food.cereals_mt({"PAK": ()})
    assert whole == food.COUNTRY_CEREALS_MT["PAK"]
    india = sum(s.food_mt for s in SUBREGIONS.values() if "IND" in s.parts)
    assert india == pytest.approx(food.COUNTRY_CEREALS_MT["IND"], abs=0.1)  # every state is in one subregion
    assert "share of India" in food.basis({"IND": ("Punjab",)})


def test_every_region_is_split_into_subregions_inside_its_season():
    assert len(SUBREGIONS) == 58
    for region in REGIONS.values():
        subregions = subregions_of(region.id)
        assert len(subregions) >= 3
        assert region_food_mt(region.id) == pytest.approx(sum(s.food_mt for s in subregions), abs=0.1)
        for sub in subregions:
            west, south, east, north = sub.bbox
            assert west < east and south < north
            assert sub.months == region.months and sub.food_mt > 0
