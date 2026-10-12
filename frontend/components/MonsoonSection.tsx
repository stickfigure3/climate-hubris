"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { API_URL, useApi } from "@/lib/api";
import { formatDate, number, seasonRange, signed } from "@/lib/format";
import type { Finding, Level, Meta, MonsoonData, Region, SeasonStats } from "@/lib/types";
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

function RegionPanel({ region, view, baseline }: { region: Region; view: View; baseline: string }) {
  const showLast = view === "last" || !region.active || region.current_season === null;
  const stats = showLast ? region.last_season : region.current_season!;
  const level: Level = showLast ? region.last_season.level : region.level;

  return (
    <div className="card region-panel">
      <div className="card-title-row">
        <h3>{region.name} monsoon</h3>
        <Status level={level} />
      </div>
      <p className="note" style={{ marginTop: 0 }}>
        Season: {seasonRange(region.season_months)} · showing {showLast ? `the ${stats.season} season` : "the season in progress"}
      </p>

      <h4>Rainfall anomaly</h4>
      <Rainfall stats={stats} />

      <h4>Seasonal rainfall against the {baseline} normal</h4>
      <AnomalyBars history={region.history} />

      <h4>Agent findings ({region.findings.length})</h4>
      {region.findings.length === 0 ? (
        <p className="note">
          The agent found no explicit statements about this monsoon in its sources for this period.
        </p>
      ) : (
        <ul className="findings">
          {region.findings.map((finding) => (
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
  const [view, setView] = useState<View | null>(null);

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
          Six monsoon systems, scored on satellite-era rainfall against the 1991–2020 normal and on what humanitarian
          and meteorological bulletins explicitly report.
        </p>
      </div>
      <div className="button-row">
        <a className="button" href={`${API_URL}/api/export/monsoon.csv`} download>
          Rainfall CSV
        </a>
        <a className="button" href={`${API_URL}/api/export/findings.csv`} download>
          Findings CSV
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
  const levelOf = (region: Region): Level => (currentView === "last" ? region.last_season.level : region.level);
  const region = data.regions.find((r) => r.id === selected) ?? data.regions[0];
  const activeNames = data.regions.filter((r) => r.active).map((r) => r.name);

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
            <MonsoonMap regions={data.regions} selected={region.id} onSelect={setSelected} levelOf={levelOf} />
            <div className="map-legend">
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
                    <th>Season</th>
                    <th className="num">Rainfall</th>
                    <th className="num">Normal</th>
                    <th className="num">Anomaly</th>
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
                          setSelected(r.id);
                          setView("last");
                        }}
                      >
                        <td>{r.name}</td>
                        <td className="nowrap">
                          {last.season}
                          {last.complete || last.months_with_data === 0 ? "" : "*"}
                        </td>
                        <td className="num">{last.observed_mm === null ? "n/a" : `${number(last.observed_mm)} mm`}</td>
                        <td className="num">{last.normal_mm === null ? "n/a" : `${number(last.normal_mm)} mm`}</td>
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

        <RegionPanel region={region} view={currentView} baseline={data.baseline} />
      </div>
    </section>
  );
}
