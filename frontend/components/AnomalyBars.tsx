"use client";

import { scaleBand, scaleLinear } from "d3-scale";
import { useState } from "react";

import { signed } from "@/lib/format";
import { useWidth } from "./useWidth";

interface Props {
  history: { season: string; start_year: number; anomaly_pct: number }[];
}

const HEIGHT = 120;
const PAD = { top: 8, bottom: 18, left: 30, right: 4 };

/** Seasonal rainfall anomaly by year: wetter than normal above the line, drier below. */
export function AnomalyBars({ history }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(360);
  const [hover, setHover] = useState<number | null>(null);
  if (history.length === 0) return <p className="note">No completed seasons on record yet.</p>;

  const extent = Math.max(20, Math.ceil(Math.max(...history.map((h) => Math.abs(h.anomaly_pct))) / 10) * 10);
  const x = scaleBand<number>()
    .domain(history.map((h) => h.start_year))
    .range([PAD.left, width - PAD.right])
    .paddingInner(0.25);
  const y = scaleLinear().domain([-extent, extent]).range([HEIGHT - PAD.bottom, PAD.top]);
  const barWidth = Math.min(24, x.bandwidth());
  const shown = hover === null ? null : history[hover];
  const first = history[0];
  const last = history[history.length - 1];

  return (
    <div>
      <div className="legend" aria-hidden="true" style={{ margin: "0 0 4px" }}>
        <span>
          <i style={{ borderColor: "var(--wet)", borderTopWidth: 8, width: 8 }} />
          Wetter than normal
        </span>
        <span>
          <i style={{ borderColor: "var(--dry)", borderTopWidth: 8, width: 8 }} />
          Drier than normal
        </span>
      </div>
      <div className="chart" ref={ref}>
        <svg
          height={HEIGHT}
          viewBox={`0 0 ${width} ${HEIGHT}`}
          role="img"
          aria-label={`Seasonal rainfall anomaly, ${first.season} to ${last.season}`}
          onPointerLeave={() => setHover(null)}
        >
          {[-extent, 0, extent].map((tick) => (
            <g key={tick}>
              <line x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? "var(--axis)" : "var(--grid)"} />
              <text x={PAD.left - 6} y={y(tick)} dy="0.32em" textAnchor="end">
                {tick > 0 ? `+${tick}` : tick}%
              </text>
            </g>
          ))}
          {history.map((h, i) => {
            const top = y(Math.max(0, h.anomaly_pct));
            const height = Math.max(1, Math.abs(y(h.anomaly_pct) - y(0)));
            const left = (x(h.start_year) ?? 0) + (x.bandwidth() - barWidth) / 2;
            return (
              <g key={h.start_year}>
                <rect
                  x={left}
                  y={top}
                  width={barWidth}
                  height={height}
                  rx={Math.min(2, barWidth / 2)}
                  fill={h.anomaly_pct >= 0 ? "var(--wet)" : "var(--dry)"}
                  opacity={hover === null || hover === i ? 1 : 0.45}
                />
                {/* Full-height hit target: short bars are hard to point at. */}
                <rect
                  x={x(h.start_year)}
                  y={PAD.top}
                  width={x.step()}
                  height={HEIGHT - PAD.top - PAD.bottom}
                  fill="transparent"
                  onPointerEnter={() => setHover(i)}
                />
              </g>
            );
          })}
          <text x={PAD.left} y={HEIGHT - 4}>
            {first.season}
          </text>
          <text x={width - PAD.right} y={HEIGHT - 4} textAnchor="end">
            {last.season}
          </text>
        </svg>
        {shown ? (
          <div
            className="tooltip"
            style={{ left: Math.min((x(shown.start_year) ?? 0) + 14, width - 160), top: 0, minWidth: 0 }}
          >
            <div className="tooltip-title">{shown.season} season</div>
            <div className="tooltip-row">
              <span>Rainfall vs normal</span>
              <b>{signed(shown.anomaly_pct)}%</b>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
