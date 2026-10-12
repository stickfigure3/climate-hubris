export interface Point {
  year: number;
  volume: number;
}

export interface HeatPoint {
  year: number;
  value: number;
}

export interface Projection {
  valid: boolean;
  reason?: string;
  disclaimer: string;
  inputs: { baseline_year: number; rate_window: number; threshold: number; layer: "700" | "2000" };
  latest_year?: number;
  rate_start_year?: number;
  volume_baseline?: number;
  volume_latest?: number;
  delta_volume?: number;
  delta_ohc?: number;
  ohc_latest?: number;
  ohc_rate_zj_per_year?: number;
  sensitivity_km3_per_zj?: number;
  volume_rate_km3_per_year?: number;
  years_to_boe?: number;
  boe_year?: number;
  path?: Point[];
  ohc_path?: HeatPoint[];
  trend: { slope_km3_per_year: number; intercept: number; zero_year: number | null; line: Point[] } | null;
}

export interface ArcticData {
  comparison: {
    date: string;
    volume: number;
    reference_date: string;
    reference_volume: number;
    difference: number;
    percent_change: number;
  } | null;
  monthly: { year: number; month: number; volume: number }[];
  annual_minima: Point[];
  ohc: Record<"700" | "2000", HeatPoint[]>;
  energy_imbalance: {
    unit: string;
    window_years: number;
    all_components_through: number | null;
    series: HeatPoint[];
  };
  projection: Projection;
  controls: {
    baseline_years: Record<"700" | "2000", number[]>;
    rate_window: { min: number; max: number; default: number };
    threshold: { min: number; max: number; default: number };
  };
}

export type Level = "normal" | "moderate" | "severe" | "unknown" | "off_season";

export interface SeasonStats {
  season: string;
  start: string;
  end: string;
  observed_mm: number | null;
  normal_mm: number | null;
  anomaly_pct: number | null;
  months_with_data: number;
  months_in_season: number;
  data_through: string | null;
  complete: boolean;
}

export interface Finding {
  date: string;
  date_basis: "document" | "published" | "retrieved";
  category: string;
  kind: "observed" | "forecast";
  severity: number;
  summary: string;
  evidence_quote: string;
  source_url: string;
  source_org: string;
  source_title: string;
}

/** Fields a region and a subregion share: both are scored the same way. */
export interface Area {
  id: string;
  name: string;
  season_months: number[];
  geometry: { type: "Polygon"; coordinates: number[][][] };
  active: boolean;
  level: Level;
  rain_level: Level | null;
  agent_level: Level | null;
  agent_severity: number | null;
  current_season: SeasonStats | null;
  last_season: SeasonStats & { level: Level; agent_severity: number | null; findings_count: number };
  findings: Finding[];
  history: { season: string; start_year: number; anomaly_pct: number }[];
  recent_months: { month: string; total_mm: number; normal_mm: number | null; complete: boolean }[];
  /** Cereal production, million tonnes a year. */
  food_mt: number;
}

export interface Region extends Area {
  hemisphere: "north" | "south";
  subregion_count: number;
}

export interface Subregion extends Area {
  region: string;
  region_name: string;
  food_share_pct: number | null;
  food_basis: string;
}

export interface RegionDetail extends Region {
  subregions: Subregion[];
}

export interface MonsoonData {
  as_of: string;
  mode: "active" | "off_season";
  active_regions: string[];
  baseline: string;
  regions: Region[];
}

export interface DatasetMeta {
  last_ingested_at?: string;
  latest_data?: string | null;
  source?: string;
  source_url?: string;
  source_last_modified?: string | null;
  status?: string;
  detail?: string;
  [key: string]: unknown;
}

export interface Meta {
  datasets: Record<string, DatasetMeta>;
  server_time: string;
}
