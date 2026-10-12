from datetime import date

import pytest

from app.ingest import climateserv, ohc, piomas

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
