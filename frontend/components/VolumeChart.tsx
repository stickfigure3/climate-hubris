"use client";

import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { useMemo, useState } from "react";

import { number } from "@/lib/format";
import type { ArcticData, Point, Projection } from "@/lib/types";
import { useWidth } from "./useWidth";

interface Props {
  monthly: ArcticData["monthly"];
  minima: Point[];
  projection: Projection;
}

const HEIGHT = 380;
const MARGIN = { top: 16, right: 24, bottom: 28, left: 40 };
const MAX_YEAR = 2100;

/** Full PIOMAS record, September minima, their linear trend, and the OHC projection to its zero crossing. */
export function VolumeChart({ monthly, minima, projection }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(720);
  const [hoverYear, setHoverYear] = useState<number | null>(null);

  const path = projection.valid ? (projection.path ?? []) : [];
  const trend = projection.trend;
  const firstYear = minima[0]?.year ?? 1979;
  const lastYear = minima[minima.length - 1]?.year ?? firstYear;
  const boeYear = projection.valid ? projection.boe_year : undefined;
  const horizon = Math.min(
    MAX_YEAR,
    Math.max(lastYear + 10, Math.ceil(Math.max(boeYear ?? 0, trend?.zero_year ?? 0) / 5) * 5 + 5),
  );

  const x = useMemo(
    () => scaleLinear().domain([firstYear, horizon]).range([MARGIN.left, width - MARGIN.right]),
    [firstYear, horizon, width],
  );
  const yMax = Math.ceil(Math.max(...monthly.map((m) => m.volume), 1) / 5) * 5;
  const y = useMemo(
    () => scaleLinear().domain([0, yMax]).range([HEIGHT - MARGIN.bottom, MARGIN.top]),
    [yMax],
  );

  const monthlyPath = useMemo(
    () =>
      line<ArcticData["monthly"][number]>()
        .x((d) => x(d.year + (d.month - 0.5) / 12))
        .y((d) => y(d.volume))(monthly) ?? "",
    [monthly, x, y],
  );
  // Annual minima sit in mid-September.
  const sept = (year: number) => x(year + 8.5 / 12);
  const pointLine = line<Point>()
    .x((d) => sept(d.year))
    .y((d) => y(d.volume));

  const minimaByYear = useMemo(() => new Map(minima.map((p) => [p.year, p.volume])), [minima]);
  const trendAt = (year: number) => (trend ? trend.intercept + (trend.slope_km3_per_year / 1000) * year : null);
  const modelAt = (year: number) => {
    if (!projection.valid || projection.volume_latest === undefined || boeYear === undefined) return null;
    if (year < lastYear || year > boeYear) return null;
    return projection.volume_latest + ((projection.volume_rate_km3_per_year ?? 0) / 1000) * (year - lastYear);
  };

  const yTicks = y.ticks(6);
  const xTicks = x.ticks(Math.max(4, Math.floor(width / 90))).filter((t) => Number.isInteger(t));
  const last = minima[minima.length - 1];
  const boeX = boeYear !== undefined ? sept(Math.min(boeYear, horizon)) : null;
  const boeOffChart = boeYear !== undefined && boeYear > horizon;

  function onMove(event: React.PointerEvent<SVGRectElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const year = Math.round(x.invert(event.clientX - bounds.left + MARGIN.left) - 8.5 / 12);
    setHoverYear(Math.max(firstYear, Math.min(horizon - 1, year)));
  }

  const hover =
    hoverYear === null
      ? null
      : { year: hoverYear, observed: minimaByYear.get(hoverYear) ?? null, trend: trendAt(hoverYear), model: modelAt(hoverYear) };
  const tooltipLeft = hover ? Math.min(sept(hover.year) + 12, width - 190) : 0;

  return (
    <div>
      <div className="legend" aria-hidden="true">
        <span>
          <i style={{ borderColor: "var(--context)", borderTopWidth: 1 }} />
          Monthly volume
        </span>
        <span>
          <i style={{ borderColor: "var(--series-1)" }} />
          Annual minimum (September)
        </span>
        <span>
          <i style={{ borderColor: "var(--text-2)", borderTopWidth: 1 }} />
          Linear trend of minima
        </span>
        <span>
          <i style={{ borderColor: "var(--series-2)", borderTopStyle: "dashed" }} />
          Ocean-heat projection
        </span>
      </div>

      <div className="chart" ref={ref}>
        <svg
          height={HEIGHT}
          viewBox={`0 0 ${width} ${HEIGHT}`}
          role="img"
          aria-label={`Arctic sea ice volume ${firstYear} to ${lastYear} with a projection of the annual minimum to zero${
            boeYear ? ` around ${Math.round(boeYear)}` : ""
          }. A data table follows the chart.`}
        >
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={width - MARGIN.right}
                y1={y(tick)}
                y2={y(tick)}
                stroke={tick === 0 ? "var(--axis)" : "var(--grid)"}
              />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
                {tick}
              </text>
            </g>
          ))}
          {xTicks.map((tick) => (
            <text key={tick} x={x(tick)} y={HEIGHT - 8} textAnchor="middle">
              {tick}
            </text>
          ))}
          <text x={MARGIN.left - 32} y={8}>
            thousand km³
          </text>

          {/* Everything right of the last observation is projection. */}
          <rect
            x={sept(lastYear)}
            y={MARGIN.top}
            width={Math.max(0, width - MARGIN.right - sept(lastYear))}
            height={HEIGHT - MARGIN.bottom - MARGIN.top}
            fill="var(--wash)"
          />
          <text x={sept(lastYear) + 8} y={MARGIN.top + 14}>
            Projection
          </text>

          <path d={monthlyPath} fill="none" stroke="var(--context)" strokeWidth={1} strokeLinejoin="round" />
          {trend ? (
            <line
              x1={sept(trend.line[0].year)}
              y1={y(trend.line[0].volume)}
              x2={sept(Math.min(trend.line[1].year, horizon))}
              y2={y(Math.max(0, trendAt(Math.min(trend.line[1].year, horizon)) ?? 0))}
              stroke="var(--text-2)"
              strokeWidth={1}
            />
          ) : null}
          <path
            d={pointLine(minima) ?? ""}
            fill="none"
            stroke="var(--series-1)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
          {path.length > 1 ? (
            <path
              d={pointLine(path.filter((p) => p.year <= horizon)) ?? ""}
              fill="none"
              stroke="var(--series-2)"
              strokeWidth={2}
              strokeDasharray="6 5"
              strokeLinecap="round"
            />
          ) : null}

          {last ? (
            <circle cx={sept(last.year)} cy={y(last.volume)} r={4.5} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
          ) : null}
          {boeX !== null && !boeOffChart ? (
            <g>
              <circle cx={boeX} cy={y(projection.inputs.threshold)} r={5} fill="var(--series-2)" stroke="var(--surface)" strokeWidth={2} />
              <text className="direct-label" x={boeX} y={y(projection.inputs.threshold) - 12} textAnchor="middle">
                ≈ {Math.round(boeYear!)}
              </text>
            </g>
          ) : null}
          {boeOffChart ? (
            <text className="direct-label" x={width - MARGIN.right} y={MARGIN.top + 14} textAnchor="end">
              Reaches zero ≈ {Math.round(boeYear!)} (beyond chart)
            </text>
          ) : null}

          {hover ? (
            <g pointerEvents="none">
              <line x1={sept(hover.year)} x2={sept(hover.year)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} stroke="var(--muted)" />
              {hover.observed !== null ? (
                <circle cx={sept(hover.year)} cy={y(hover.observed)} r={4.5} fill="var(--series-1)" stroke="var(--surface)" strokeWidth={2} />
              ) : null}
              {hover.model !== null ? (
                <circle cx={sept(hover.year)} cy={y(hover.model)} r={4.5} fill="var(--series-2)" stroke="var(--surface)" strokeWidth={2} />
              ) : null}
            </g>
          ) : null}

          <rect
            x={MARGIN.left}
            y={MARGIN.top}
            width={Math.max(0, width - MARGIN.left - MARGIN.right)}
            height={HEIGHT - MARGIN.top - MARGIN.bottom}
            fill="transparent"
            onPointerMove={onMove}
            onPointerLeave={() => setHoverYear(null)}
          />
        </svg>

        {hover ? (
          <div className="tooltip" style={{ left: tooltipLeft, top: MARGIN.top + 8 }}>
            <div className="tooltip-title">September {hover.year}</div>
            {hover.observed !== null ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--series-1)" }} />
                  Observed minimum
                </span>
                <b>{number(hover.observed * 1000)} km³</b>
              </div>
            ) : null}
            {hover.model !== null && hover.year > lastYear ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--series-2)" }} />
                  Ocean-heat projection
                </span>
                <b>{number(Math.max(0, hover.model) * 1000)} km³</b>
              </div>
            ) : null}
            {hover.trend !== null ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--text-2)" }} />
                  Linear trend
                </span>
                <b>{number(Math.max(0, hover.trend) * 1000)} km³</b>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <details className="table-view">
        <summary>View annual minima as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Year</th>
                <th className="num">Minimum volume (km³)</th>
                <th className="num">Linear trend (km³)</th>
              </tr>
            </thead>
            <tbody>
              {[...minima].reverse().map((p) => (
                <tr key={p.year}>
                  <td>{p.year}</td>
                  <td className="num">{number(p.volume * 1000)}</td>
                  <td className="num">{number((trendAt(p.year) ?? 0) * 1000)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
