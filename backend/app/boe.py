"""Blue Ocean Event projection.

A deliberately simple, first-order model: assume the loss of September sea ice
volume since a baseline year scales linearly with the ocean heat gained over the
same period, extend ocean heat forward in a straight line at its recent rate of
increase, and read off when the ice that heat implies hits a threshold.

Volumes are in 10^3 km^3 (PIOMAS convention); ocean heat content is in ZJ (10^21 J).
"""

from __future__ import annotations

from typing import Any

DISCLAIMER = (
    "This is a first-order estimate based on a linear relationship. It does not account "
    "for non-linear feedbacks, albedo changes, or abrupt ice loss events."
)

# By default ocean heat is extended at its average rate of increase since this year,
# and the dashboard lets that window be moved between these limits.
RATE_FROM_YEAR = 2020
RATE_WINDOW_MIN = 3
RATE_WINDOW_MAX = 6

# The seasonal minimum falls in September; a year only counts once the months
# around it have been published.
_MIN_MONTHS = (7, 8, 9)  # zero-based Aug, Sep, Oct


def annual_minima(monthly: dict[int, list[float | None]]) -> dict[int, float]:
    """Annual minimum monthly volume, for years where the minimum has been observed."""
    out: dict[int, float] = {}
    for year, values in sorted(monthly.items()):
        if any(values[m] is None for m in _MIN_MONTHS):
            continue
        out[year] = min(v for v in values if v is not None)
    return out


def linear_fit(points: dict[int, float]) -> dict[str, float] | None:
    """Ordinary least squares of value on year."""
    n = len(points)
    if n < 2:
        return None
    xs, ys = list(points.keys()), list(points.values())
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    return {"slope": slope, "intercept": intercept}


def default_rate_window(latest_year: int) -> int:
    """Years back to RATE_FROM_YEAR, kept inside the limits the dashboard offers."""
    return max(RATE_WINDOW_MIN, min(RATE_WINDOW_MAX, latest_year - RATE_FROM_YEAR))


def project_boe(
    minima: dict[int, float],
    ohc: dict[int, float],
    baseline_year: int | None = None,
    rate_window: int | None = None,
    threshold: float = 0.0,
) -> dict[str, Any]:
    """Project the year the annual-minimum volume reaches `threshold`.

    sensitivity   = dV / dOHC                between baseline_year and the latest common year
    ohc_rate      = mean annual OHC increase over the last `rate_window` years
    OHC(t)        = OHC_latest + ohc_rate * (t - latest)
    V(t)          = V_latest + sensitivity * (OHC(t) - OHC_latest)
    years_to_boe  = (V_latest - threshold) / (|sensitivity| * ohc_rate)

    The baseline defaults to the first year both records cover, and the rate
    window to the years since RATE_FROM_YEAR.
    """
    common = sorted(set(minima) & set(ohc))
    if common:
        baseline_year = common[0] if baseline_year is None else baseline_year
        rate_window = default_rate_window(common[-1]) if rate_window is None else rate_window
    result: dict[str, Any] = {
        "inputs": {
            "baseline_year": baseline_year,
            "rate_window": rate_window,
            "threshold": threshold,
        },
        "disclaimer": DISCLAIMER,
        "valid": False,
    }
    if not common:
        return {**result, "reason": "No year has both a sea ice minimum and an ocean heat value."}

    latest = common[-1]
    if baseline_year not in minima or baseline_year not in ohc:
        return {**result, "reason": f"No data for baseline year {baseline_year}."}
    if baseline_year >= latest:
        return {**result, "reason": "Baseline year must be earlier than the latest data year."}
    rate_start = latest - rate_window
    if rate_window < 1 or rate_start not in ohc:
        return {**result, "reason": f"No ocean heat value for {rate_start}."}

    d_volume = minima[latest] - minima[baseline_year]
    d_ohc = ohc[latest] - ohc[baseline_year]
    ohc_rate = (ohc[latest] - ohc[rate_start]) / rate_window
    result.update(
        latest_year=latest,
        rate_start_year=rate_start,
        volume_baseline=minima[baseline_year],
        volume_latest=minima[latest],
        ohc_baseline=ohc[baseline_year],
        ohc_latest=ohc[latest],
        delta_volume=d_volume,
        delta_ohc=d_ohc,
        ohc_rate_zj_per_year=ohc_rate,
    )
    if d_ohc <= 0 or d_volume >= 0:
        return {
            **result,
            "reason": "Ice volume did not fall while ocean heat rose over this window, "
            "so the model has no sensitivity to project with.",
        }
    if ohc_rate <= 0:
        return {**result, "reason": "Ocean heat content did not increase over the rate window."}

    sensitivity = d_volume / d_ohc  # 10^3 km^3 per ZJ, negative
    volume_rate = sensitivity * ohc_rate  # 10^3 km^3 per year, negative
    remaining = minima[latest] - threshold
    if remaining <= 0:
        return {**result, "valid": True, "years_to_boe": 0.0, "boe_year": float(latest),
                "sensitivity_km3_per_zj": sensitivity * 1000,
                "volume_rate_km3_per_year": volume_rate * 1000, "path": [], "ohc_path": []}

    years = remaining / -volume_rate
    boe_year = latest + years
    path = [{"year": latest, "volume": minima[latest]}]
    for y in range(latest + 1, int(boe_year) + 1):
        path.append({"year": y, "volume": minima[latest] + volume_rate * (y - latest)})
    path.append({"year": round(boe_year, 2), "volume": threshold})
    # The heat the ice path is read from: the same years, on the straight line.
    ohc_path = [{"year": p["year"], "value": ohc[latest] + ohc_rate * (p["year"] - latest)} for p in path[:-1]]
    ohc_path.append({"year": round(boe_year, 2), "value": ohc[latest] + ohc_rate * years})

    result.update(
        valid=True,
        sensitivity_km3_per_zj=sensitivity * 1000,
        volume_rate_km3_per_year=volume_rate * 1000,
        years_to_boe=years,
        boe_year=boe_year,
        path=path,
        ohc_path=ohc_path,
    )
    return result


def trend_projection(minima: dict[int, float], threshold: float = 0.0) -> dict[str, Any] | None:
    """Plain linear trend through every annual minimum, for comparison with the OHC model."""
    fit = linear_fit(minima)
    if fit is None:
        return None
    years = sorted(minima)
    crossing = None
    if fit["slope"] < 0:
        crossing = (threshold - fit["intercept"]) / fit["slope"]
    end = int(crossing) + 1 if crossing else years[-1]
    return {
        "slope_km3_per_year": fit["slope"] * 1000,
        "intercept": fit["intercept"],
        "zero_year": crossing,
        "line": [
            {"year": y, "volume": fit["intercept"] + fit["slope"] * y}
            for y in (years[0], end)
        ],
    }
