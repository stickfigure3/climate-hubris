import type { Level } from "@/lib/types";

export const LEVEL_LABEL: Record<Level, string> = {
  normal: "Normal",
  moderate: "Moderate stress",
  severe: "Severe stress",
  unknown: "No data yet",
  off_season: "Off-season",
};

export const LEVEL_COLOR: Record<Level, string> = {
  normal: "#0ca30c",
  moderate: "#fab219",
  severe: "#d03b3b",
  unknown: "#898781",
  off_season: "#898781",
};

export function Status({ level }: { level: Level }) {
  return (
    <span className={`status ${level}`}>
      <span className="swatch" />
      {LEVEL_LABEL[level]}
    </span>
  );
}
