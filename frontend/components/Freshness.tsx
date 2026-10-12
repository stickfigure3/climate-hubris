"use client";

import { daysSince, formatDate, timeAgo } from "@/lib/format";
import type { Meta } from "@/lib/types";

interface Props {
  meta: Meta | null;
  dataset: string;
  /** Days after which the newest value counts as overdue for this source's publishing cadence. */
  staleAfterDays: number;
  label?: string;
  /** Shown when the source cannot be reached, where there is no date to label. */
  name?: string;
}

/** "Data through X, checked Y ago", flagged when the source is overdue or unreachable. */
export function Freshness({ meta, dataset, staleAfterDays, label = "Data through", name }: Props) {
  if (!meta) return <div className="freshness">Checking data freshness…</div>;
  const info = meta.datasets[dataset];
  if (!info) {
    return (
      <div className="freshness down">
        <span className="dot" />
        <span className="flag">{name ? `${name}: not ingested yet` : "Not ingested yet"}</span>
      </div>
    );
  }

  const down = info.status === "unavailable" || info.status === "error";
  const age = daysSince(info.latest_data);
  const stale = !down && age !== null && age > staleAfterDays;

  return (
    <div className={`freshness${down ? " down" : stale ? " stale" : ""}`}>
      <span className="dot" />
      {down ? (
        <span className="flag">{name ? `${name}: source unavailable` : "Source unavailable"}</span>
      ) : (
        <span>
          {label} {formatDate(info.latest_data)}
        </span>
      )}
      {stale ? <span className="flag">Source has not published for {age} days</span> : null}
      <span>Checked {timeAgo(info.last_ingested_at)}</span>
    </div>
  );
}
