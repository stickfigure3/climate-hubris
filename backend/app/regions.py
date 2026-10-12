"""Monsoon regions and their seasons."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from . import food


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



@dataclass(frozen=True)
class Subregion:
    """A state, group of states or country inside a monsoon region.

    Scored exactly like its region, over its own box and the region's season.
    `parts` says what it is made of, for the food production estimate: ISO3
    country -> states, an empty tuple meaning the whole country.
    """

    id: str  # "<region>.<slug>"
    name: str
    bbox: tuple[float, float, float, float]
    parts: dict[str, tuple[str, ...]]

    @property
    def region(self) -> str:
        return self.id.split(".")[0]

    @property
    def months(self) -> tuple[int, ...]:
        return REGIONS[self.region].months

    @property
    def polygon(self) -> dict:
        w, s, e, n = self.bbox
        return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}

    @property
    def food_mt(self) -> float:
        return food.cereals_mt(self.parts)

    @property
    def countries(self) -> tuple[str, ...]:
        return tuple(self.parts)


def _sub(region: str, slug: str, name: str, bbox: tuple[float, float, float, float], **parts) -> Subregion:
    return Subregion(f"{region}.{slug}", name, bbox, {c: tuple(units) for c, units in parts.items()})


# Subregions follow borders that statistics are published for: countries, and states
# or provinces of the three largest producers, with small producers merged into their
# neighbours so that no subregion is a rounding error next to another. Boxes cover the
# farmed core of each and overlap at the edges, as the region boxes do.
SUBREGIONS: dict[str, Subregion] = {
    s.id: s
    for s in (
        # South Asia
        _sub("south_asia", "punjab_haryana", "Punjab & Haryana", (73.9, 27.7, 77.6, 32.5),
             IND=("Punjab", "Haryana", "Himachal Pradesh", "Jammu & Kashmir")),
        _sub("south_asia", "uttar_pradesh", "Uttar Pradesh", (77.1, 23.9, 84.6, 30.4),
             IND=("Uttar Pradesh", "Uttarakhand")),
        _sub("south_asia", "bihar_jharkhand", "Bihar & Jharkhand", (83.3, 21.9, 88.3, 27.5),
             IND=("Bihar", "Jharkhand")),
        _sub("south_asia", "west_bengal", "West Bengal", (86.0, 21.6, 89.9, 27.2), IND=("West Bengal", "Sikkim")),
        _sub("south_asia", "northeast_india", "Assam & the Northeast", (89.8, 23.0, 96.0, 28.2),
             IND=("Assam", "Tripura", "Meghalaya", "Manipur", "Arunachal Pradesh", "Nagaland", "Mizoram")),
        _sub("south_asia", "rajasthan_gujarat", "Rajasthan & Gujarat", (68.2, 20.1, 78.2, 30.2),
             IND=("Rajasthan", "Gujarat")),
        _sub("south_asia", "madhya_pradesh", "Madhya Pradesh", (74.0, 21.1, 82.8, 26.9), IND=("Madhya Pradesh",)),
        _sub("south_asia", "chhattisgarh_odisha", "Chhattisgarh & Odisha", (80.2, 17.8, 87.5, 24.1),
             IND=("Chhattisgarh", "Odisha")),
        _sub("south_asia", "maharashtra", "Maharashtra", (72.6, 15.6, 80.9, 22.0), IND=("Maharashtra", "Goa")),
        _sub("south_asia", "telangana_andhra", "Telangana & Andhra Pradesh", (76.7, 12.6, 84.8, 19.9),
             IND=("Telangana", "Andhra Pradesh")),
        _sub("south_asia", "south_india", "Karnataka, Tamil Nadu & Kerala", (74.0, 8.1, 80.4, 18.4),
             IND=("Karnataka", "Tamil Nadu", "Kerala")),
        _sub("south_asia", "pakistan", "Pakistan", (66.5, 24.0, 75.4, 34.5), PAK=()),
        _sub("south_asia", "bangladesh", "Bangladesh", (88.0, 21.5, 92.7, 26.6), BGD=()),
        _sub("south_asia", "nepal", "Nepal", (80.0, 26.3, 88.2, 30.4), NPL=()),
        _sub("south_asia", "sri_lanka", "Sri Lanka", (79.6, 5.9, 81.9, 9.9), LKA=()),
        # East Asia
        _sub("east_asia", "heilongjiang", "Heilongjiang", (122.0, 43.5, 134.5, 50.0), CHN=("Heilongjiang",)),
        _sub("east_asia", "jilin_liaoning", "Jilin & Liaoning", (118.9, 38.8, 131.2, 46.2),
             CHN=("Jilin", "Liaoning")),
        _sub("east_asia", "inner_mongolia", "Inner Mongolia", (106.0, 38.0, 123.0, 47.0), CHN=("Inner Mongolia",)),
        _sub("east_asia", "hebei", "Hebei, Beijing & Tianjin", (113.5, 36.1, 119.8, 41.5),
             CHN=("Hebei", "Beijing", "Tianjin")),
        _sub("east_asia", "shanxi_shaanxi", "Shanxi & Shaanxi", (105.5, 31.7, 114.6, 40.7),
             CHN=("Shanxi", "Shaanxi")),
        _sub("east_asia", "shandong", "Shandong", (114.8, 34.4, 122.7, 38.4), CHN=("Shandong",)),
        _sub("east_asia", "henan", "Henan", (110.4, 31.4, 116.7, 36.4), CHN=("Henan",)),
        _sub("east_asia", "lower_yangtze", "Jiangsu, Anhui & Zhejiang", (114.9, 27.1, 122.9, 35.1),
             CHN=("Jiangsu", "Anhui", "Zhejiang", "Shanghai")),
        _sub("east_asia", "middle_yangtze", "Hubei, Hunan & Jiangxi", (108.4, 24.5, 118.5, 33.3),
             CHN=("Hubei", "Hunan", "Jiangxi")),
        _sub("east_asia", "sichuan_chongqing", "Sichuan & Chongqing", (102.0, 28.0, 110.2, 32.8),
             CHN=("Sichuan", "Chongqing")),
        _sub("east_asia", "yunnan_guizhou", "Yunnan & Guizhou", (97.5, 21.1, 109.6, 29.2),
             CHN=("Yunnan", "Guizhou")),
        _sub("east_asia", "south_china", "Guangdong, Guangxi & Fujian", (104.5, 20.2, 120.3, 27.5),
             CHN=("Guangdong", "Guangxi", "Fujian", "Hainan")),
        _sub("east_asia", "korea", "Korean Peninsula", (124.5, 34.0, 130.6, 43.0), KOR=(), PRK=()),
        _sub("east_asia", "japan", "Japan", (129.5, 31.0, 142.0, 41.5), JPN=()),
        # West Africa
        _sub("west_africa", "nigeria", "Nigeria", (2.7, 4.3, 14.7, 13.9), NGA=()),
        _sub("west_africa", "niger", "Niger", (0.2, 11.7, 13.5, 16.0), NER=()),
        _sub("west_africa", "mali", "Mali", (-11.5, 10.2, -3.2, 15.5), MLI=()),
        _sub("west_africa", "burkina_faso", "Burkina Faso", (-5.5, 9.4, 2.4, 15.1), BFA=()),
        _sub("west_africa", "ghana", "Ghana", (-3.3, 4.7, 1.2, 11.2), GHA=()),
        _sub("west_africa", "cote_divoire", "Côte d’Ivoire", (-8.6, 4.4, -2.5, 10.7), CIV=()),
        _sub("west_africa", "senegal_gambia", "Senegal & Gambia", (-17.5, 12.3, -11.4, 16.7), SEN=(), GMB=()),
        _sub("west_africa", "guinea_coast", "Guinea, Sierra Leone & Liberia", (-15.1, 4.4, -7.6, 12.7),
             GIN=(), SLE=(), LBR=(), GNB=()),
        _sub("west_africa", "benin_togo", "Benin & Togo", (-0.2, 6.1, 3.9, 12.4), BEN=(), TGO=()),
        _sub("west_africa", "chad", "Chad", (13.5, 7.4, 22.0, 14.5), TCD=()),
        # Australia
        _sub("australia", "queensland", "Queensland", (138.0, -28.0, 153.0, -11.0), AUS=("Queensland",)),
        _sub("australia", "top_end", "Top End (Northern Territory)", (129.0, -18.0, 138.0, -11.0),
             AUS=("Northern Territory",)),
        _sub("australia", "kimberley", "Kimberley (Western Australia)", (120.5, -19.5, 129.0, -13.7),
             AUS=("Kimberley",)),
        # South America
        _sub("south_america", "mato_grosso", "Mato Grosso", (-61.6, -18.0, -50.2, -7.4), BRA=("Mato Grosso",)),
        _sub("south_america", "mato_grosso_do_sul", "Mato Grosso do Sul", (-58.2, -24.1, -50.9, -17.2),
             BRA=("Mato Grosso do Sul",)),
        _sub("south_america", "goias_tocantins", "Goiás & Tocantins", (-53.3, -19.5, -45.7, -5.2),
             BRA=("Goiás", "Tocantins", "Distrito Federal")),
        _sub("south_america", "minas_sao_paulo", "Minas Gerais & São Paulo", (-53.1, -25.3, -39.9, -14.2),
             BRA=("Minas Gerais", "São Paulo")),
        _sub("south_america", "matopiba", "Bahia, Maranhão & Piauí", (-48.5, -16.0, -38.0, -2.5),
             BRA=("Bahia", "Maranhão", "Piauí")),
        _sub("south_america", "parana", "Paraná", (-54.6, -26.7, -48.0, -22.5), BRA=("Paraná",)),
        _sub("south_america", "paraguay", "Paraguay", (-62.6, -27.6, -54.3, -19.3), PRY=()),
        _sub("south_america", "bolivia", "Bolivia", (-66.0, -21.5, -58.0, -12.0), BOL=()),
        # Southern Africa
        _sub("southern_africa", "south_africa", "South Africa", (24.0, -30.5, 31.5, -24.5), ZAF=()),
        _sub("southern_africa", "tanzania", "Tanzania", (29.5, -11.7, 40.4, -4.5), TZA=()),
        _sub("southern_africa", "madagascar", "Madagascar", (43.2, -25.6, 50.5, -12.0), MDG=()),
        _sub("southern_africa", "malawi", "Malawi", (32.7, -17.1, 35.9, -9.4), MWI=()),
        _sub("southern_africa", "angola", "Angola", (12.0, -17.5, 22.0, -7.0), AGO=()),
        _sub("southern_africa", "zambia", "Zambia", (22.0, -18.0, 33.7, -8.2), ZMB=()),
        _sub("southern_africa", "mozambique", "Mozambique", (30.2, -26.9, 40.8, -10.5), MOZ=()),
        _sub("southern_africa", "zimbabwe", "Zimbabwe", (25.2, -22.4, 33.1, -15.6), ZWE=()),
    )
}


def subregions_of(region_id: str) -> list[Subregion]:
    return [s for s in SUBREGIONS.values() if s.region == region_id]


def region_food_mt(region_id: str) -> float:
    """A region grows what its subregions grow."""
    return round(sum(s.food_mt for s in subregions_of(region_id)), 1)


# Every box rainfall is collected for: the six regions, then their subregions.
AREAS: dict[str, Region | Subregion] = {**REGIONS, **SUBREGIONS}

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


def season_starting(region: Region | Subregion, start_year: int) -> Season:
    """The season whose first month falls in `start_year`."""
    pairs, year, prev = [], start_year, region.months[0]
    for m in region.months:
        if m < prev:  # wrapped past December
            year += 1
        pairs.append((year, m))
        prev = m
    return Season(start_year, tuple(pairs))


def current_season(region: Region | Subregion, today: date) -> Season | None:
    """The season in progress on `today`, or None between seasons."""
    for start_year in (today.year, today.year - 1):
        season = season_starting(region, start_year)
        if season.start <= today <= season.end:
            return season
    return None


def last_completed_season(region: Region | Subregion, today: date) -> Season:
    for start_year in (today.year, today.year - 1, today.year - 2):
        season = season_starting(region, start_year)
        if season.end < today:
            return season
    raise AssertionError("unreachable: a season always ended within two years")
