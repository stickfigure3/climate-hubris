"use client";

import { scaleLinear } from "d3-scale";
import { line } from "d3-shape";
import { useState } from "react";

import { signed } from "@/lib/format";
import type { HeatPoint } from "@/lib/types";
import { useWidth } from "./useWidth";

interface Props {
  points: HeatPoint[];
  /** Years averaged into each point. */
  windowYears: number;
  /** Last year with every component measured; later years rest on ocean heat alone. */
  measuredThrough: number | null;
}

const HEIGHT = 150;
const PAD = { top: 10, right: 10, bottom: 20, left: 34 };

/** Net energy imbalance only: one line against a W/m² axis, with zero (in balance) marked. */
export function ImbalanceChart({ points, windowYears, measuredThrough }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(300);
  const [index, setIndex] = useState<number | null>(null);
  if (points.length < 2) return <p className="note">Energy imbalance has not been ingested yet.</p>;

  const first = points[0];
  const last = points[points.length - 1];
  const top = Math.max(1, Math.ceil(Math.max(...points.map((p) => p.value)) * 2) / 2);
  const bottom = Math.min(0, Math.floor(Math.min(...points.map((p) => p.value)) * 2) / 2);
  const x = scaleLinear().domain([first.year, last.year]).range([PAD.left, width - PAD.right]);
  const y = scaleLinear().domain([bottom, top]).range([HEIGHT - PAD.bottom, PAD.top]);
  const path = line<HeatPoint>().x((d) => x(d.year)).y((d) => y(d.value));
  const split = measuredThrough ?? last.year;
  const shown = points[index ?? points.length - 1];
  const ticks = y.ticks(4);

  function onMove(event: React.PointerEvent<SVGRectElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const year = x.invert(event.clientX - bounds.left + PAD.left);
    let nearest = 0;
    points.forEach((p, i) => {
      if (Math.abs(p.year - year) < Math.abs(points[nearest].year - year)) nearest = i;
    });
    setIndex(nearest);
  }

  return (
    <div className="chart" ref={ref}>
      <svg
        height={HEIGHT}
        viewBox={`0 0 ${width} ${HEIGHT}`}
        role="img"
        aria-label={`Earth's net energy imbalance in watts per square metre, ${windowYears}-year mean, ${first.year} to ${last.year}. Latest value ${signed(last.value, 2)}.`}
      >
        {ticks.map((tick) => (
          <g key={tick}>
            <line x1={PAD.left} x2={width - PAD.right} y1={y(tick)} y2={y(tick)} stroke={tick === 0 ? "var(--axis)" : "var(--grid)"} />
            <text x={PAD.left - 6} y={y(tick)} dy="0.32em" textAnchor="end">
              {tick === 0 ? "0" : signed(tick, 1)}
            </text>
          </g>
        ))}
        <text x={PAD.left} y={HEIGHT - 4}>
          {first.year}
        </text>
        <text x={width - PAD.right} y={HEIGHT - 4} textAnchor="end">
          {last.year}
        </text>

        <path
          d={path(points.filter((p) => p.year <= split)) ?? ""}
          fill="none"
          stroke="var(--series-3)"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* Years the source has published for the ocean only. */}
        <path
          d={path(points.filter((p) => p.year >= split)) ?? ""}
          fill="none"
          stroke="var(--series-3)"
          strokeWidth={2}
          strokeDasharray="5 4"
          strokeLinecap="round"
        />
        {index !== null ? (
          <line x1={x(shown.year)} x2={x(shown.year)} y1={PAD.top} y2={HEIGHT - PAD.bottom} stroke="var(--muted)" pointerEvents="none" />
        ) : null}
        <circle cx={x(shown.year)} cy={y(shown.value)} r={4.5} fill="var(--series-3)" stroke="var(--surface)" strokeWidth={2} pointerEvents="none" />
        <rect
          x={PAD.left}
          y={PAD.top}
          width={Math.max(0, width - PAD.left - PAD.right)}
          height={HEIGHT - PAD.top - PAD.bottom}
          fill="transparent"
          onPointerMove={onMove}
          onPointerLeave={() => setIndex(null)}
        />
      </svg>
      <div className="note" style={{ marginTop: 2 }}>
        {shown.year - windowYears}–{shown.year}:{" "}
        <strong style={{ color: "var(--text)" }}>{signed(shown.value, 2)} W/m²</strong>
        {shown.year > split ? " · from ocean heat alone" : ""}
      </div>
    </div>
  );
}
