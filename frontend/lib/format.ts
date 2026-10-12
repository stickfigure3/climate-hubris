const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-02-28" -> "28 Feb 2026"; "2026-08" -> "Aug 2026"; "2025" -> "2025". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "n/a";
  const [year, month, day] = value.slice(0, 10).split("-");
  if (!month) return year;
  const name = MONTHS[Number(month) - 1];
  return day ? `${Number(day)} ${name} ${year}` : `${name} ${year}`;
}

export function monthName(month: number): string {
  return MONTHS[month - 1];
}

export function seasonRange(months: number[]): string {
  return `${monthName(months[0])}–${monthName(months[months.length - 1])}`;
}

export function timeAgo(iso: string | undefined, now: Date = new Date()): string {
  if (!iso) return "never";
  const minutes = Math.round((now.getTime() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

/** Whole days between an ISO date (or month, or year) and now. */
export function daysSince(value: string | null | undefined, now: Date = new Date()): number | null {
  if (!value) return null;
  const [year, month = "12", day = "28"] = value.slice(0, 10).split("-");
  const then = Date.UTC(Number(year), Number(month) - 1, Number(day));
  return Math.floor((now.getTime() - then) / 86400000);
}

export function signed(value: number, digits = 1): string {
  const text = Math.abs(value).toFixed(digits);
  return `${value < 0 ? "−" : "+"}${text}`;
}

export function number(value: number, digits = 0): string {
  return value.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
