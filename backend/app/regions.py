"""Monsoon regions and their seasons."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    months: tuple[int, ...]  # in season order, e.g. (12, 1, 2, 3)
    bbox: tuple[float, float, float, float]  # west, south, east, north
    hemisphere: str

    @property
    def polygon(self) -> dict:
        w, s, e, n = self.bbox
        return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


# Boxes over the core monsoon land area of each system. They are coarse on purpose:
# the stress score is a regional average, not a district-level product.
REGIONS: dict[str, Region] = {
    r.id: r
    for r in (
        Region("south_asia", "South Asian (India)", (6, 7, 8, 9), (68, 8, 90, 30), "north"),
        Region("east_asia", "East Asian", (5, 6, 7, 8, 9), (100, 20, 125, 40), "north"),
        Region("west_africa", "West African", (6, 7, 8, 9), (-18, 5, 15, 18), "north"),
        Region("australia", "Australian", (12, 1, 2, 3), (120, -20, 146, -10), "south"),
        Region("south_america", "South American", (12, 1, 2, 3), (-65, -25, -40, -5), "south"),
        Region("southern_africa", "Southern African", (11, 12, 1, 2, 3), (20, -25, 40, -10), "south"),
    )
}

# Months in which the dashboard leads with the "Last Season Summary" panel.
OFF_SEASON_MONTHS = (4, 5, 10, 11)


@dataclass(frozen=True)
class Season:
    start_year: int
    months: tuple[tuple[int, int], ...]  # (year, month) pairs in order

    @property
    def label(self) -> str:
        end_year = self.months[-1][0]
        if end_year == self.start_year:
            return str(self.start_year)
        return f"{self.start_year}–{str(end_year)[2:]}"

    @property
    def keys(self) -> list[str]:
        return [f"{y}-{m:02d}" for y, m in self.months]

    @property
    def end(self) -> date:
        y, m = self.months[-1]
        return date(y, m, calendar.monthrange(y, m)[1])

    @property
    def start(self) -> date:
        y, m = self.months[0]
        return date(y, m, 1)


def season_starting(region: Region, start_year: int) -> Season:
    """The season whose first month falls in `start_year`."""
    pairs, year, prev = [], start_year, region.months[0]
    for m in region.months:
        if m < prev:  # wrapped past December
            year += 1
        pairs.append((year, m))
        prev = m
    return Season(start_year, tuple(pairs))


def current_season(region: Region, today: date) -> Season | None:
    """The season in progress on `today`, or None between seasons."""
    for start_year in (today.year, today.year - 1):
        season = season_starting(region, start_year)
        if season.start <= today <= season.end:
            return season
    return None


def last_completed_season(region: Region, today: date) -> Season:
    for start_year in (today.year, today.year - 1, today.year - 2):
        season = season_starting(region, start_year)
        if season.end < today:
            return season
    raise AssertionError("unreachable: a season always ended within two years")
