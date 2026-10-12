"""Rough cereal production for each monsoon subregion.

One definition everywhere: cereals as FAO counts them (rice as paddy), in million
tonnes a year. A country is the World Bank / FAO figure, averaged over 2022-2024.
A group of states or provinces is its country's figure multiplied by the group's
share of the national total in that country's own statistics. The national
statistics measure slightly different baskets (India's foodgrains include pulses,
China's grain includes tubers and soybeans), so they are used for shares only.

These are sizing estimates for the map, good to roughly ten percent, not a
production dataset.
"""

from __future__ import annotations

# World Bank indicator AG.PRD.CREL.MT (source: FAO), mean of 2022, 2023 and 2024, million tonnes.
COUNTRY_CEREALS_MT: dict[str, float] = {
    "AGO": 3.34, "AUS": 51.69, "BEN": 2.65, "BFA": 5.18, "BGD": 65.27, "BOL": 3.15, "BRA": 143.53,
    "CHN": 641.35, "CIV": 3.60, "GHA": 5.67, "GIN": 5.14, "GMB": 0.11, "GNB": 0.31, "IND": 372.82,
    "JPN": 11.54, "KOR": 5.11, "LBR": 0.30, "LKA": 4.45, "MDG": 5.26, "MLI": 10.24, "MOZ": 2.65,
    "MWI": 3.70, "NER": 5.66, "NGA": 28.95, "NPL": 11.27, "PAK": 52.51, "PRK": 4.82, "PRY": 6.30,
    "SEN": 3.86, "SLE": 1.49, "TCD": 2.72, "TGO": 1.50, "TZA": 13.40, "ZAF": 17.46, "ZMB": 2.83,
    "ZWE": 1.44,
}
COUNTRY_SOURCE = "World Bank AG.PRD.CREL.MT (FAO), 2022–2024 mean"

# Total foodgrains by state, 2023-24, lakh tonnes (Ministry of Agriculture & Farmers Welfare).
INDIA_FOODGRAINS: dict[str, float] = {
    "Uttar Pradesh": 592.9, "Madhya Pradesh": 398.4, "Punjab": 325.9, "Rajasthan": 231.9, "Bihar": 200.4,
    "Telangana": 198.4, "West Bengal": 188.2, "Haryana": 184.5, "Maharashtra": 145.3, "Karnataka": 127.3,
    "Odisha": 110.0, "Chhattisgarh": 107.0, "Gujarat": 100.8, "Tamil Nadu": 92.7, "Andhra Pradesh": 90.0,
    "Assam": 54.6, "Jharkhand": 35.6, "Uttarakhand": 17.3, "Himachal Pradesh": 15.3, "Jammu & Kashmir": 15.0,
    "Tripura": 8.0, "Kerala": 7.0, "Meghalaya": 5.0, "Manipur": 4.0, "Arunachal Pradesh": 3.0,
    "Nagaland": 3.0, "Mizoram": 2.0, "Sikkim": 1.0, "Goa": 0.9,
}

# Grain output by province, 2024, 10,000 tonnes (National Bureau of Statistics of China).
CHINA_GRAIN: dict[str, float] = {
    "Beijing": 57.6, "Tianjin": 270.6, "Hebei": 3908.8, "Shanxi": 1468.7, "Inner Mongolia": 4100.5,
    "Liaoning": 2500.3, "Jilin": 4266.0, "Heilongjiang": 8001.7, "Shanghai": 98.3, "Jiangsu": 3810.1,
    "Zhejiang": 650.2, "Anhui": 4184.3, "Fujian": 514.4, "Jiangxi": 2196.0, "Shandong": 5710.2,
    "Henan": 6719.4, "Hubei": 2785.3, "Hunan": 3078.1, "Guangdong": 1313.4, "Guangxi": 1403.8,
    "Hainan": 142.4, "Chongqing": 1100.7, "Sichuan": 3633.8, "Guizhou": 1146.1, "Yunnan": 1993.5,
    "Xizang": 112.9, "Shaanxi": 1352.3, "Gansu": 1296.1, "Qinghai": 118.3, "Ningxia": 385.9,
    "Xinjiang": 2330.2,
}

# Maize, rice and wheat by state, 2023, million tonnes (IBGE Produção Agrícola Municipal, table 5457).
BRAZIL_CEREALS: dict[str, float] = {
    "Mato Grosso": 50.57, "Paraná": 21.67, "Goiás": 14.68, "Rio Grande do Sul": 13.69,
    "Mato Grosso do Sul": 13.62, "Minas Gerais": 8.77, "São Paulo": 5.36, "Santa Catarina": 4.05,
    "Bahia": 3.12, "Tocantins": 3.00, "Piauí": 2.85, "Maranhão": 2.67, "Pará": 1.86, "Rondônia": 1.82,
    "Sergipe": 0.91, "Ceará": 0.38, "Distrito Federal": 0.32, "Roraima": 0.17, "Acre": 0.14,
    "Alagoas": 0.09, "Espírito Santo": 0.07, "Pernambuco": 0.05, "Paraíba": 0.04,
    "Rio Grande do Norte": 0.03, "Amazonas": 0.02, "Rio de Janeiro": 0.01,
}

# Australia's monsoon belt grows almost no grain. Queensland is wheat 2.2 + barley 0.5 +
# sorghum 1.7 million tonnes (ABARES Australian Crop Report, 2024-25). No published figure
# was found for the Northern Territory or the Kimberley; 0.05 stands for "negligible".
AUSTRALIA_CEREALS_MT: dict[str, float] = {"Queensland": 4.4, "Northern Territory": 0.05, "Kimberley": 0.05}

_NATIONAL = {
    "IND": (INDIA_FOODGRAINS, "share of India's 2023–24 foodgrains (Ministry of Agriculture)"),
    "CHN": (CHINA_GRAIN, "share of China's 2024 grain output (National Bureau of Statistics)"),
    "BRA": (BRAZIL_CEREALS, "share of Brazil's 2023 maize, rice and wheat (IBGE)"),
}


def cereals_mt(parts: dict[str, tuple[str, ...]]) -> float:
    """Cereal production of a subregion made of whole countries and groups of states.

    `parts` maps an ISO3 country code to the states it contributes; an empty tuple
    means the whole country.
    """
    total = 0.0
    for country, units in parts.items():
        if country == "AUS":
            total += sum(AUSTRALIA_CEREALS_MT[u] for u in units)
        elif units:
            table, _ = _NATIONAL[country]
            total += COUNTRY_CEREALS_MT[country] * sum(table[u] for u in units) / sum(table.values())
        else:
            total += COUNTRY_CEREALS_MT[country]
    return round(total, 2)


def basis(parts: dict[str, tuple[str, ...]]) -> str:
    """One line saying where a subregion's estimate comes from."""
    notes = []
    for country, units in parts.items():
        if country == "AUS":
            notes.append("ABARES Australian Crop Report 2024–25; negligible outside Queensland")
        elif units:
            notes.append(f"{COUNTRY_SOURCE}, scaled by {_NATIONAL[country][1]}")
        elif COUNTRY_SOURCE not in notes:
            notes.append(COUNTRY_SOURCE)
    return "; ".join(notes)
