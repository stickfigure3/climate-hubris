"use client";

import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { useMemo, useState } from "react";

import { number, signed } from "@/lib/format";
import type { ArcticData, HeatPoint, Point, Projection } from "@/lib/types";
import { useWidth } from "./useWidth";

interface Props {
  monthly: ArcticData["monthly"];
  minima: Point[];
  /** Ocean heat content for the layer the projection uses, in ZJ. */
  ohc: HeatPoint[];
  projection: Projection;
}

const HEIGHT = 400;
const MARGIN = { top: 26, right: 50, bottom: 28, left: 40 };
const MAX_YEAR = 2100;

/**
 * Full PIOMAS record, September minima and their linear trend on the left axis; ocean heat
 * content on the right axis, extended in a straight line; and the ice path that heat implies.
 */
export function VolumeChart({ monthly, minima, ohc, projection }: Props) {
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
  const layer = projection.inputs.layer === "2000" ? "0–2000 m" : "0–700 m";

  const x = useMemo(
    () => scaleLinear().domain([firstYear, horizon]).range([MARGIN.left, width - MARGIN.right]),
    [firstYear, horizon, width],
  );
  const yMax = Math.ceil(Math.max(...monthly.map((m) => m.volume), 1) / 5) * 5;
  const y = useMemo(
    () => scaleLinear().domain([0, yMax]).range([HEIGHT - MARGIN.bottom, MARGIN.top]),
    [yMax],
  );

  // Ocean heat: observed annual means, then a straight line at the recent rate of increase.
  const heat = useMemo(() => ohc.filter((p) => p.year >= firstYear), [ohc, firstYear]);
  const heatFrom = projection.latest_year ?? heat[heat.length - 1]?.year ?? lastYear;
  const heatRate = projection.ohc_rate_zj_per_year;
  const heatProjected = (year: number) =>
    projection.ohc_latest === undefined || heatRate === undefined || year < heatFrom
      ? null
      : projection.ohc_latest + heatRate * (year - heatFrom);
  const heatEnd = heatProjected(horizon);
  const heatValues = [...heat.map((p) => p.value), ...(heatEnd === null ? [] : [heatEnd])];
  const heatMin = Math.floor(Math.min(0, ...heatValues) / 50) * 50;
  const heatMax = Math.max(heatMin + 50, Math.ceil(Math.max(...heatValues, 0) / 50) * 50);
  const yHeat = useMemo(
    () => scaleLinear().domain([heatMin, heatMax]).range([HEIGHT - MARGIN.bottom, MARGIN.top]),
    [heatMin, heatMax],
  );

  const monthlyPath = useMemo(
    () =>
      line<ArcticData["monthly"][number]>()
        .x((d) => x(d.year + (d.month - 0.5) / 12))
        .y((d) => y(d.volume))(monthly) ?? "",
    [monthly, x, y],
  );
  // Annual minima sit in mid-September; annual mean ocean heat sits mid-year. Both share the year axis.
  const sept = (year: number) => x(year + 8.5 / 12);
  const midYear = (year: number) => x(year + 0.5);
  const pointLine = line<Point>()
    .x((d) => sept(d.year))
    .y((d) => y(d.volume));
  const heatLine = line<HeatPoint>()
    .x((d) => midYear(d.year))
    .y((d) => yHeat(d.value));

  const minimaByYear = useMemo(() => new Map(minima.map((p) => [p.year, p.volume])), [minima]);
  const heatByYear = useMemo(() => new Map(heat.map((p) => [p.year, p.value])), [heat]);
  const trendAt = (year: number) => (trend ? trend.intercept + (trend.slope_km3_per_year / 1000) * year : null);
  const modelAt = (year: number) => {
    if (!projection.valid || projection.volume_latest === undefined || boeYear === undefined) return null;
    if (year < lastYear || year > boeYear) return null;
    return projection.volume_latest + ((projection.volume_rate_km3_per_year ?? 0) / 1000) * (year - lastYear);
  };

  const yTicks = y.ticks(6);
  const heatTicks = yHeat.ticks(6);
  const xTicks = x.ticks(Math.max(4, Math.floor(width / 90))).filter((t) => Number.isInteger(t));
  const last = minima[minima.length - 1];
  const lastHeat = heat[heat.length - 1];
  const boeX = boeYear !== undefined ? sept(Math.min(boeYear, horizon)) : null;
  const boeOffChart = boeYear !== undefined && boeYear > horizon;
  const right = width - MARGIN.right;

  function onMove(event: React.PointerEvent<SVGRectElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const year = Math.round(x.invert(event.clientX - bounds.left + MARGIN.left) - 8.5 / 12);
    setHoverYear(Math.max(firstYear, Math.min(horizon - 1, year)));
  }

  const hover =
    hoverYear === null
      ? null
      : {
          year: hoverYear,
          observed: minimaByYear.get(hoverYear) ?? null,
          trend: trendAt(hoverYear),
          model: modelAt(hoverYear),
          heat: heatByYear.get(hoverYear) ?? null,
          heatProjected: hoverYear > heatFrom ? heatProjected(hoverYear) : null,
        };
  const tooltipLeft = hover ? Math.min(sept(hover.year) + 12, width - 240) : 0;

  return (
    <div>
      <div className="legend" aria-hidden="true">
        <span>
          <i style={{ borderColor: "var(--context)", borderTopWidth: 1 }} />
          Monthly ice volume
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
          Ice implied by projected ocean heat
        </span>
        <span>
          <i style={{ borderColor: "var(--series-3)" }} />
          Ocean heat content, {layer} (right axis)
        </span>
        <span>
          <i style={{ borderColor: "var(--series-3)", borderTopStyle: "dashed" }} />
          Ocean heat at its {projection.rate_start_year ?? "recent"}–{heatFrom} rate
        </span>
      </div>

      <div className="chart" ref={ref}>
        <svg
          height={HEIGHT}
          viewBox={`0 0 ${width} ${HEIGHT}`}
          role="img"
          aria-label={`Arctic sea ice volume ${firstYear} to ${lastYear} on the left axis and global ocean heat content on the right axis, with ocean heat extended in a straight line and the annual ice minimum it implies falling to zero${
            boeYear ? ` around ${Math.round(boeYear)}` : ""
          }. A data table follows the chart.`}
        >
          {yTicks.map((tick) => (
            <g key={tick}>
              <line
                x1={MARGIN.left}
                x2={right}
                y1={y(tick)}
                y2={y(tick)}
                stroke={tick === 0 ? "var(--axis)" : "var(--grid)"}
              />
              <text x={MARGIN.left - 8} y={y(tick)} dy="0.32em" textAnchor="end">
                {tick}
              </text>
            </g>
          ))}
          {/* Right axis: ocean heat. Ticks only, so the grid stays the ice axis's. */}
          {heat.length > 1
            ? heatTicks.map((tick) => (
                <g key={tick}>
                  <line x1={right} x2={right + 4} y1={yHeat(tick)} y2={yHeat(tick)} stroke="var(--axis)" />
                  <text x={right + 8} y={yHeat(tick)} dy="0.32em">
                    {tick}
                  </text>
                </g>
              ))
            : null}
          {xTicks.map((tick) => (
            <text key={tick} x={x(tick)} y={HEIGHT - 8} textAnchor="middle">
              {tick}
            </text>
          ))}
          <rect x={MARGIN.left - 32} y={3} width={8} height={8} rx={2} fill="var(--series-1)" />
          <text x={MARGIN.left - 20} y={11}>
            Ice volume, thousand km³
          </text>
          {heat.length > 1 ? (
            <>
              <text x={right + 30} y={11} textAnchor="end">
                Ocean heat, ZJ
              </text>
              <rect x={right + 34} y={3} width={8} height={8} rx={2} fill="var(--series-3)" />
            </>
          ) : null}

          {/* Everything right of the last observation is projection. */}
          <rect
            x={sept(lastYear)}
            y={MARGIN.top}
            width={Math.max(0, right - sept(lastYear))}
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

          {heat.length > 1 ? (
            <path
              d={heatLine(heat) ?? ""}
              fill="none"
              stroke="var(--series-3)"
              strokeWidth={2}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ) : null}
          {heatEnd !== null && projection.ohc_latest !== undefined ? (
            <line
              x1={midYear(heatFrom)}
              y1={yHeat(projection.ohc_latest)}
              x2={midYear(horizon - 0.5)}
              y2={yHeat(heatProjected(horizon - 0.5) ?? heatEnd)}
              stroke="var(--series-3)"
              strokeWidth={2}
              strokeDasharray="6 5"
              strokeLinecap="round"
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

          {lastHeat ? (
            <circle cx={midYear(lastHeat.year)} cy={yHeat(lastHeat.value)} r={4.5} fill="var(--series-3)" stroke="var(--surface)" strokeWidth={2} />
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
            <text className="direct-label" x={right} y={MARGIN.top + 14} textAnchor="end">
              Reaches zero ≈ {Math.round(boeYear!)} (beyond chart)
            </text>
          ) : null}

          {hover ? (
            <g pointerEvents="none">
              <line x1={sept(hover.year)} x2={sept(hover.year)} y1={MARGIN.top} y2={HEIGHT - MARGIN.bottom} stroke="var(--muted)" />
              {hover.heat !== null ? (
                <circle cx={midYear(hover.year)} cy={yHeat(hover.heat)} r={4.5} fill="var(--series-3)" stroke="var(--surface)" strokeWidth={2} />
              ) : null}
              {hover.heatProjected !== null ? (
                <circle cx={midYear(hover.year)} cy={yHeat(hover.heatProjected)} r={4.5} fill="var(--series-3)" stroke="var(--surface)" strokeWidth={2} />
              ) : null}
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
          <div className="tooltip" style={{ left: Math.max(0, tooltipLeft), top: MARGIN.top + 8 }}>
            <div className="tooltip-title">{hover.year}</div>
            {hover.observed !== null ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--series-1)" }} />
                  September ice minimum
                </span>
                <b>{number(hover.observed * 1000)} km³</b>
              </div>
            ) : null}
            {hover.model !== null && hover.year > lastYear ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--series-2)" }} />
                  Ice implied by ocean heat
                </span>
                <b>{number(Math.max(0, hover.model) * 1000)} km³</b>
              </div>
            ) : null}
            {hover.trend !== null ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--text-2)" }} />
                  Linear trend of ice
                </span>
                <b>{number(Math.max(0, hover.trend) * 1000)} km³</b>
              </div>
            ) : null}
            {hover.heat !== null ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--series-3)" }} />
                  Ocean heat content
                </span>
                <b>{signed(hover.heat, 0)} ZJ</b>
              </div>
            ) : null}
            {hover.heatProjected !== null ? (
              <div className="tooltip-row">
                <span>
                  <span className="key" style={{ background: "var(--series-3)" }} />
                  Ocean heat, projected
                </span>
                <b>{signed(hover.heatProjected, 0)} ZJ</b>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>

      <details className="table-view">
        <summary>View annual minima and ocean heat as a table</summary>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Year</th>
                <th className="num">Minimum volume (km³)</th>
                <th className="num">Linear trend (km³)</th>
                <th className="num">Ocean heat, {layer} (ZJ)</th>
              </tr>
            </thead>
            <tbody>
              {[...minima].reverse().map((p) => (
                <tr key={p.year}>
                  <td>{p.year}</td>
                  <td className="num">{number(p.volume * 1000)}</td>
                  <td className="num">{number((trendAt(p.year) ?? 0) * 1000)}</td>
                  <td className="num">{heatByYear.has(p.year) ? signed(heatByYear.get(p.year)!, 1) : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
