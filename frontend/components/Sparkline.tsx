"use client";

import { scaleLinear } from "d3-scale";
import { area, line } from "d3-shape";
import { useState } from "react";

import { useWidth } from "./useWidth";

interface Props {
  points: { year: number; value: number }[];
  height?: number;
  format: (value: number) => string;
  label: string;
}

/** One series, no axes: the shape of a trend, with the hovered or latest value read out beside it. */
export function Sparkline({ points, height = 64, format, label }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>(280);
  const [index, setIndex] = useState<number | null>(null);
  if (points.length < 2) return null;

  const pad = 6;
  const values = points.map((p) => p.value);
  const x = scaleLinear().domain([points[0].year, points[points.length - 1].year]).range([pad, width - pad]);
  const y = scaleLinear().domain([Math.min(...values), Math.max(...values)]).range([height - pad, pad]);
  const path = line<Props["points"][number]>().x((d) => x(d.year)).y((d) => y(d.value))(points) ?? "";
  const fill = area<Props["points"][number]>().x((d) => x(d.year)).y0(height).y1((d) => y(d.value))(points) ?? "";
  const shown = points[index ?? points.length - 1];

  function onMove(event: React.PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const year = x.invert(event.clientX - bounds.left);
    let nearest = 0;
    points.forEach((p, i) => {
      if (Math.abs(p.year - year) < Math.abs(points[nearest].year - year)) nearest = i;
    });
    setIndex(nearest);
  }

  return (
    <div className="chart" ref={ref}>
      <svg
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${label}, ${points[0].year} to ${points[points.length - 1].year}`}
        onPointerMove={onMove}
        onPointerLeave={() => setIndex(null)}
      >
        <path d={fill} fill="var(--series-2)" opacity={0.1} />
        <path d={path} fill="none" stroke="var(--series-2)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(shown.year)} cy={y(shown.value)} r={4} fill="var(--series-2)" stroke="var(--surface)" strokeWidth={2} />
      </svg>
      <div className="note" style={{ marginTop: 2 }}>
        {shown.year}: <strong style={{ color: "var(--text)" }}>{format(shown.value)}</strong>
        {index === null ? ` · since ${points[0].year}` : ""}
      </div>
    </div>
  );
}
