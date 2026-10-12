"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { API_URL, useApi } from "@/lib/api";
import { formatDate, number, seasonRange, signed } from "@/lib/format";
import type { Area, Finding, Level, Meta, MonsoonData, Region, RegionDetail, SeasonStats, Subregion } from "@/lib/types";
import { AnomalyBars } from "./AnomalyBars";
import { Freshness } from "./Freshness";
import { Status } from "./status";

// Leaflet touches `window` on import, so the map only loads in the browser.
const MonsoonMap = dynamic(() => import("./MonsoonMap"), {
  ssr: false,
  loading: () => <div className="map skeleton">Loading map…</div>,
});

type View = "live" | "last";

const CATEGORY_LABEL: Record<string, string> = {
  monsoon_failure: "Monsoon failure or delay",
  below_average_rainfall: "Below-average rainfall",
  drought: "Drought",
  flooding: "Flooding",
  near_normal: "Near-normal rains",
};

function severityClass(severity: number): string {
  return severity >= 7 ? "sev-severe" : severity >= 4 ? "sev-moderate" : "";
}

function Rainfall({ stats }: { stats: SeasonStats }) {
  if (stats.anomaly_pct === null || stats.observed_mm === null || stats.normal_mm === null) {
    return <p className="note">No rainfall data has been published for the {stats.season} season yet.</p>;
  }
  return (
    <>
      <div className="figure">
        {signed(stats.anomaly_pct)}%<small>vs normal</small>
      </div>
      <p className="note">
        {number(stats.observed_mm)} mm fell against a normal of {number(stats.normal_mm)} mm
        {stats.complete
          ? ` over the full ${stats.season} season.`
          : ` for ${stats.months_with_data} of ${stats.months_in_season} season months (data through ${formatDate(stats.data_through)}).`}
      </p>
    </>
  );
}

function FindingItem({ finding }: { finding: Finding }) {
  return (
    <li className={`finding ${finding.kind === "forecast" ? "" : severityClass(finding.severity)}`}>
      <div>
        <span className="tag">{finding.kind === "forecast" ? "Forecast" : "Reported"}</span>
        <span className="tag">Severity {finding.severity}/10</span>
        {CATEGORY_LABEL[finding.category] ?? finding.category}
      </div>
      <div>{finding.summary}</div>
      <blockquote>“{finding.evidence_quote}”</blockquote>
      <div className="finding-meta">
        <a href={finding.source_url} target="_blank" rel="noreferrer">
          {finding.source_org}
        </a>{" "}
        · {finding.date_basis === "retrieved" ? "retrieved" : "dated"} {formatDate(finding.date)}
      </div>
    </li>
  );
}

/** Cereal tonnage: one decimal below ten million tonnes, whole numbers above. */
function cereals(mt: number): string {
  return `${number(mt, mt < 10 ? 1 : 0)} Mt`;
}

function SubregionTable({
  subregions,
  levelOf,
  statsOf,
  onSelect,
}: {
  subregions: Subregion[];
  levelOf: (area: Area) => Level;
  statsOf: (area: Area) => SeasonStats;
  onSelect: (id: string) => void;
}) {
  const largest = Math.max(...subregions.map((s) => s.food_mt), 1e-9);
  return (
    <div className="table-scroll" style={{ maxHeight: 420 }}>
      <table className="subregions">
        <thead>
          <tr>
            <th>Subregion</th>
            <th className="num">Cereals a year</th>
            <th className="num">Rainfall</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {subregions.map((sub) => {
            const stats = statsOf(sub);
            return (
              <tr key={sub.id} className="clickable" onClick={() => onSelect(sub.id)}>
                <td>
                  <button className="link-button" style={{ color: "var(--text)", textAlign: "left" }}>
                    {sub.name}
                  </button>
                </td>
                <td className="num">
                  {cereals(sub.food_mt)}
                  <span className="share" title={`${sub.food_share_pct}% of the region`}>
                    <i style={{ width: `${(sub.food_mt / largest) * 100}%` }} />
                  </span>
                </td>
                <td className="num">{stats.anomaly_pct === null ? "n/a" : `${signed(stats.anomaly_pct)}%`}</td>
                <td>
                  <Status level={levelOf(sub)} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface PanelProps {
  area: Region | Subregion;
  view: View;
  baseline: string;
  /** Share of the six regions' cereals, for a region. */
  worldShare?: number;
  /** A region's subregions, once loaded. */
  subregions?: Subregion[] | null;
  subregionsError?: string | null;
  levelOf: (area: Area) => Level;
  onSelectSubregion: (id: string) => void;
  onBack: () => void;
}

/** One box's detail. Regions and subregions are scored the same way, so they share the panel. */
function AreaPanel({ area, view, baseline, worldShare, subregions, subregionsError, levelOf, onSelectSubregion, onBack }: PanelProps) {
  const showLast = view === "last" || !area.active || area.current_season === null;
  const statsOf = (a: Area): SeasonStats => (showLast || a.current_season === null ? a.last_season : a.current_season);
  const stats = statsOf(area);
  const level: Level = showLast ? area.last_season.level : area.level;
  const sub = "region" in area ? area : null;

  return (
    <div className="card region-panel">
      {sub ? (
        <p className="crumb">
          <button className="link-button" onClick={onBack}>
            ← {sub.region_name.replace(" (India)", "")} monsoon
          </button>
        </p>
      ) : null}
      <div className="card-title-row">
        <h3>{sub ? area.name : `${area.name} monsoon`}</h3>
        <Status level={level} />
      </div>
      <p className="note" style={{ marginTop: 0 }}>
        Season: {seasonRange(area.season_months)} · showing {showLast ? `the ${stats.season} season` : "the season in progress"}
      </p>

      <h4>Food grown under this monsoon</h4>
      <div className="figure">
        {number(area.food_mt, area.food_mt < 10 ? 1 : 0)}
        <small>million tonnes of cereals a year</small>
      </div>
      <p className="note">
        {sub
          ? `About ${sub.food_share_pct}% of the ${sub.region_name.replace(" (India)", "")} region’s cereals. Estimate: ${sub.food_basis}.`
          : `About ${number(worldShare ?? 0)}% of the cereals grown across the six monsoon regions, summed from ${
              (area as Region).subregion_count
            } subregions.`}
      </p>

      <h4>Rainfall anomaly</h4>
      <Rainfall stats={stats} />

      <h4>Seasonal rainfall against the {baseline} normal</h4>
      <AnomalyBars history={area.history} />

      {sub ? null : (
        <>
          <h4>Subregions, largest producer first</h4>
          {subregions ? (
            <SubregionTable subregions={subregions} levelOf={levelOf} statsOf={statsOf} onSelect={onSelectSubregion} />
          ) : (
            <p className="note">{subregionsError ? `Subregions could not be loaded: ${subregionsError}` : "Loading subregions…"}</p>
          )}
        </>
      )}

      <h4>Agent findings ({area.findings.length})</h4>
      {area.findings.length === 0 ? (
        <p className="note">
          {sub
            ? "The agent found no explicit statements about this subregion in its sources for this period."
            : "The agent found no explicit statements about this monsoon in its sources for this period."}
        </p>
      ) : (
        <ul className="findings">
          {area.findings.map((finding) => (
            <FindingItem key={`${finding.source_url}-${finding.evidence_quote.slice(0, 40)}`} finding={finding} />
          ))}
        </ul>
      )}
    </div>
  );
}

export function MonsoonSection({ meta }: { meta: Meta | null }) {
  const monsoon = useApi<MonsoonData>("/api/monsoon");
  const [selected, setSelected] = useState<string | null>(null);
  // The map is either the world, or zoomed into the selected region to show its subregions.
  const [zoomed, setZoomed] = useState(false);
  const [subregion, setSubregion] = useState<string | null>(null);
  const [view, setView] = useState<View | null>(null);
  const detail = useApi<RegionDetail>(selected ? `/api/monsoon/${selected}` : null);

  const data = monsoon.data;
  useEffect(() => {
    if (!data) return;
    setView((current) => current ?? (data.mode === "off_season" ? "last" : "live"));
    setSelected((current) => current ?? data.active_regions[0] ?? data.regions[0]?.id ?? null);
  }, [data]);

  const head = (
    <div className="section-head">
      <div>
        <h2>Global monsoon monitor</h2>
        <p>
          Six monsoon systems and the 58 subregions inside them, scored on satellite-era rainfall against the
          1991–2020 normal and on what humanitarian and meteorological bulletins explicitly report. Each box is sized
          by the cereals grown there.
        </p>
      </div>
      <div className="button-row">
        <a className="button" href={`${API_URL}/api/export/monsoon.csv`} download>
          Rainfall CSV
        </a>
        <a className="button" href={`${API_URL}/api/export/findings.csv`} download>
          Findings CSV
        </a>
        <a className="button" href={`${API_URL}/api/export/food.csv`} download>
          Food production CSV
        </a>
      </div>
    </div>
  );

  if (!data) {
    return (
      <section className="section" id="monsoon">
        {head}
        {monsoon.error ? (
          <div className="banner error">Monsoon data could not be loaded: {monsoon.error}</div>
        ) : (
          <div className="card skeleton">Loading monsoon data…</div>
        )}
      </section>
    );
  }

  const currentView: View = view ?? "live";
  const levelOf = (area: Area): Level => (currentView === "last" ? area.last_season.level : area.level);
  const region = data.regions.find((r) => r.id === selected) ?? data.regions[0];
  const activeNames = data.regions.filter((r) => r.active).map((r) => r.name);
  // useApi keeps the previous region's answer while the next one loads; only use a matching one.
  const subregions = detail.data?.id === region.id ? detail.data.subregions : null;
  const chosen = subregions?.find((s) => s.id === subregion) ?? null;
  const totalFood = data.regions.reduce((sum, r) => sum + r.food_mt, 0);

  function selectRegion(id: string) {
    setSelected(id);
    setSubregion(null);
    setZoomed(true);
  }

  function selectSubregion(id: string) {
    setSubregion(id);
    setZoomed(true);
  }

  return (
    <section className="section" id="monsoon">
      {head}

      <div className="banner">
        {data.mode === "off_season" ? (
          <>
            <strong>Off-season.</strong>{" "}
            {activeNames.length === 0
              ? "No monsoon is in its core season this month, so the map shows how each region's most recent season ended."
              : `Only the ${activeNames.join(" and ")} monsoon is active this month, so the map leads with how each region's most recent season ended.`}
          </>
        ) : (
          <>
            <strong>In season:</strong> {activeNames.join(", ")}. Regions outside their season are outlined in grey.
          </>
        )}
      </div>

      <div className="grid map-and-panel">
        <div className="grid">
          <div className="card map-card">
            <MonsoonMap
              regions={data.regions}
              focus={zoomed ? { region, subregions } : null}
              selected={zoomed ? subregion : region.id}
              onSelectRegion={selectRegion}
              onSelectSubregion={selectSubregion}
              onBack={() => {
                setZoomed(false);
                setSubregion(null);
              }}
              levelOf={levelOf}
            />
            <div className="map-legend">
              <p className="map-caption">
                {zoomed
                  ? `${region.name.replace(" (India)", "")} subregions. Box area shows each one’s share of the region’s cereals; click a box for its detail.`
                  : "Box area shows cereals grown under each monsoon, in million tonnes (Mt) a year. Click a region to see its subregions."}
              </p>
              <Status level="normal" />
              <Status level="moderate" />
              <Status level="severe" />
              <Status level={currentView === "last" ? "unknown" : "off_season"} />
              <div className="segmented" style={{ marginLeft: "auto" }}>
                <button aria-pressed={currentView === "live"} onClick={() => setView("live")}>
                  Live conditions
                </button>
                <button aria-pressed={currentView === "last"} onClick={() => setView("last")}>
                  Last season
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <h3>Last season summary</h3>
            <div className="table-scroll" style={{ maxHeight: "none" }}>
              <table>
                <thead>
                  <tr>
                    <th>Region</th>
                    <th className="num">Cereals a year</th>
                    <th>Season</th>
                    <th className="num">Rainfall</th>
                    <th className="num">Against normal</th>
                    <th className="num">Reports</th>
                    <th>Outcome</th>
                  </tr>
                </thead>
                <tbody>
                  {data.regions.map((r) => {
                    const last = r.last_season;
                    return (
                      <tr
                        key={r.id}
                        className={`clickable${r.id === region.id ? " selected" : ""}`}
                        onClick={() => {
                          selectRegion(r.id);
                          setView("last");
                        }}
                      >
                        <td>{r.name}</td>
                        <td className="num">{cereals(r.food_mt)}</td>
                        <td className="nowrap">
                          {last.season}
                          {last.complete || last.months_with_data === 0 ? "" : "*"}
                        </td>
                        <td className="num">{last.observed_mm === null ? "n/a" : `${number(last.observed_mm)} mm`}</td>
                        <td className="num">{last.anomaly_pct === null ? "n/a" : `${signed(last.anomaly_pct)}%`}</td>
                        <td className="num">{last.findings_count}</td>
                        <td>
                          <Status level={last.level} />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {data.regions.some((r) => !r.last_season.complete && r.last_season.months_with_data > 0) ? (
              <p className="note">
                * Rainfall for the final months has not been published yet; the comparison covers the months available.
              </p>
            ) : null}
            <Freshness meta={meta} dataset="monsoon_rainfall" staleAfterDays={75} label="CHIRPS rainfall through" />
            <Freshness meta={meta} dataset="agent" staleAfterDays={21} label="Agent last read its sources on" name="Agent" />
            <Freshness meta={meta} dataset="imd_statewise" staleAfterDays={14} label="IMD state rainfall through" name="IMD state rainfall (India)" />
          </div>
        </div>

        <AreaPanel
          area={chosen ?? region}
          view={currentView}
          baseline={data.baseline}
          worldShare={totalFood ? (region.food_mt / totalFood) * 100 : 0}
          subregions={subregions}
          subregionsError={detail.error}
          levelOf={levelOf}
          onSelectSubregion={selectSubregion}
          onBack={() => setSubregion(null)}
        />
      </div>
    </section>
  );
}
