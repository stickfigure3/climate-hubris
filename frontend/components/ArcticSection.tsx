"use client";

import { useEffect, useState } from "react";

import { API_URL, useApi } from "@/lib/api";
import { formatDate, number, signed } from "@/lib/format";
import type { ArcticData, Meta, Projection } from "@/lib/types";
import { Freshness } from "./Freshness";
import { Sparkline } from "./Sparkline";
import { VolumeChart } from "./VolumeChart";

type Layer = "700" | "2000";

interface Assumptions {
  baseline: number;
  window: number;
  layer: Layer;
  threshold: number;
}

const DEFAULTS: Assumptions = { baseline: 2000, window: 10, layer: "700", threshold: 0 };

export function ArcticSection({ meta }: { meta: Meta | null }) {
  const arctic = useApi<ArcticData>("/api/arctic");
  const [assumptions, setAssumptions] = useState<Assumptions>(DEFAULTS);
  // Sliders fire continuously; ask the API only once the value settles.
  const [settled, setSettled] = useState<Assumptions>(DEFAULTS);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(assumptions), 250);
    return () => clearTimeout(timer);
  }, [assumptions]);

  const isDefault = JSON.stringify(settled) === JSON.stringify(DEFAULTS);
  const custom = useApi<Projection>(
    isDefault
      ? null
      : `/api/arctic/projection?baseline_year=${settled.baseline}&rate_window=${settled.window}&layer=${settled.layer}&threshold=${settled.threshold}`,
  );

  if (arctic.error && !arctic.data) {
    return (
      <section className="section" id="arctic">
        <div className="section-head">
          <h2>Arctic sea ice</h2>
        </div>
        <div className="banner error">Sea ice data could not be loaded: {arctic.error}</div>
      </section>
    );
  }
  if (!arctic.data) {
    return (
      <section className="section" id="arctic">
        <div className="section-head">
          <h2>Arctic sea ice</h2>
        </div>
        <div className="card skeleton">Loading sea ice data…</div>
      </section>
    );
  }

  const data = arctic.data;
  const projection = isDefault ? data.projection : (custom.data ?? data.projection);
  const comparison = data.comparison;
  const ohc = data.ohc["700"];
  const baselineYears = data.controls.baseline_years[assumptions.layer];
  const update = (patch: Partial<Assumptions>) => setAssumptions((a) => ({ ...a, ...patch }));

  function setLayer(layer: Layer) {
    const years = data.controls.baseline_years[layer];
    const baseline = years.includes(assumptions.baseline) ? assumptions.baseline : years[0];
    // The 0-2000 m record starts in 2005, so earlier baselines fall back to its first year.
    update({ layer, baseline });
  }

  return (
    <section className="section" id="arctic">
      <div className="section-head">
        <div>
          <h2>Arctic sea ice</h2>
          <p>
            How much ice is left compared with the year 2000, and when a simple ocean-heat model says the September
            minimum reaches zero: a Blue Ocean Event.
          </p>
        </div>
        <a className="button" href={`${API_URL}/api/export/arctic.csv`} download>
          Download CSV
        </a>
      </div>

      <div className="grid three">
        <div className="card">
          <h3>
            Ice volume on the same date
            {comparison ? `, ${Number(comparison.date.slice(0, 4)) - Number(comparison.reference_date.slice(0, 4))} years apart` : ""}
          </h3>
          {comparison ? (
            <>
              <div className="pair">
                <div>
                  <div className="label">{formatDate(comparison.date)}</div>
                  <div className="figure">
                    {number(comparison.volume * 1000)}
                    <small>km³</small>
                  </div>
                </div>
                <div>
                  <div className="label">{formatDate(comparison.reference_date)}</div>
                  <div className="figure">
                    {number(comparison.reference_volume * 1000)}
                    <small>km³</small>
                  </div>
                </div>
              </div>
              <div className="delta-row">
                <span>
                  <strong>
                    {comparison.difference < 0 ? "\u2212" : "+"}
                    {number(Math.abs(comparison.difference) * 1000)} km³
                  </strong>{" "}
                  difference
                </span>
                <span>
                  <strong>{signed(comparison.percent_change)}%</strong> change
                </span>
              </div>
            </>
          ) : (
            <p className="note">Daily volume has not been ingested yet.</p>
          )}
          <Freshness meta={meta} dataset="piomas_daily" staleAfterDays={45} label="Latest PIOMAS day:" />
        </div>

        <div className="card">
          <h3>Projected first ice-free September</h3>
          {projection.valid && projection.boe_year !== undefined ? (
            <>
              <div className="hero-figure">
                {Math.round(projection.boe_year)}
                <small>in about {Math.round(projection.years_to_boe ?? 0)} years</small>
              </div>
              <p className="note">
                First-order estimate from ocean heat uptake.{" "}
                {projection.trend?.zero_year
                  ? `A straight line through the September minima reaches zero in ${Math.round(projection.trend.zero_year)}.`
                  : ""}
              </p>
            </>
          ) : (
            <p className="note">{projection.reason ?? "No projection available."}</p>
          )}
          <Freshness meta={meta} dataset="piomas_monthly" staleAfterDays={75} label="Monthly volume through" />
        </div>

        <div className="card">
          <h3>Global ocean heat content, 0–700 m</h3>
          <Sparkline
            points={ohc}
            label="Ocean heat content anomaly in zettajoules"
            format={(v) => `${signed(v, 0)} ZJ vs 1955–2006 mean`}
          />
          <Freshness meta={meta} dataset="ohc_700" staleAfterDays={640} label="Annual mean through" />
        </div>
      </div>

      <div className="disclaimer" role="note">
        <div>
          <strong>Read this before quoting the date.</strong>
          {projection.disclaimer}
        </div>
      </div>

      <div className="grid chart-and-controls">
        <div className="card">
          <div className="card-title-row">
            <h3>Sea ice volume, 1979 to present, and the path to zero</h3>
          </div>
          <VolumeChart monthly={data.monthly} minima={data.annual_minima} projection={projection} />
        </div>

        <div className="card">
          <div className="card-title-row" style={{ marginBottom: 12 }}>
            <h3>Projection assumptions</h3>
            {isDefault ? null : (
              <button className="link-button" onClick={() => setAssumptions(DEFAULTS)}>
                Reset
              </button>
            )}
          </div>
          <div className="controls">
            <div className="control">
              <label htmlFor="baseline">Sensitivity measured since</label>
              <select id="baseline" value={assumptions.baseline} onChange={(e) => update({ baseline: Number(e.target.value) })}>
                {baselineYears.map((year) => (
                  <option key={year} value={year}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
            <div className="control">
              <label htmlFor="window">
                Heat uptake averaged over
                <output>last {assumptions.window} years</output>
              </label>
              <input
                id="window"
                type="range"
                min={data.controls.rate_window.min}
                max={data.controls.rate_window.max}
                value={assumptions.window}
                onChange={(e) => update({ window: Number(e.target.value) })}
              />
            </div>
            <div className="control">
              <div className="control-label">Ocean layer</div>
              <div className="segmented">
                {(["700", "2000"] as Layer[]).map((layer) => (
                  <button key={layer} aria-pressed={assumptions.layer === layer} onClick={() => setLayer(layer)}>
                    0–{layer} m
                  </button>
                ))}
              </div>
            </div>
            <div className="control">
              <label htmlFor="threshold">
                Count as ice-free below
                <output>{number(assumptions.threshold * 1000)} km³</output>
              </label>
              <input
                id="threshold"
                type="range"
                min={0}
                max={2}
                step={0.25}
                value={assumptions.threshold}
                onChange={(e) => update({ threshold: Number(e.target.value) })}
              />
            </div>

            {projection.valid ? (
              <dl className="model-facts">
                <dt>Ice lost per ZJ of ocean heat</dt>
                <dd>{number(Math.abs(projection.sensitivity_km3_per_zj ?? 0), 1)} km³</dd>
                <dt>Ocean heat gained per year</dt>
                <dd>{number(projection.ohc_rate_zj_per_year ?? 0, 1)} ZJ</dd>
                <dt>Implied ice loss per year</dt>
                <dd>{number(Math.abs(projection.volume_rate_km3_per_year ?? 0))} km³</dd>
                <dt>September {projection.latest_year} minimum</dt>
                <dd>{number((projection.volume_latest ?? 0) * 1000)} km³</dd>
              </dl>
            ) : (
              <p className="note">{projection.reason}</p>
            )}
            {custom.error && !isDefault ? <p className="note">Could not recompute: {custom.error}</p> : null}
          </div>
        </div>
      </div>
    </section>
  );
}
