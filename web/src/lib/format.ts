// Dates and times as the owner reads them: New York time, written out in words.
// The pipeline's schedule is New York time too (docs/decisions.md, decision 14).

export const TIMEZONE = "America/New_York";

const dateTime = new Intl.DateTimeFormat("en-US", {
  timeZone: TIMEZONE,
  weekday: "short",
  month: "short",
  day: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

// Calendar dates (YYYY-MM-DD) have no time zone; format them as-is.
const calendarDate = new Intl.DateTimeFormat("en-US", {
  timeZone: "UTC",
  month: "short",
  day: "numeric",
  year: "numeric",
});

/** "Tue, Oct 20, 6:00 AM" (New York time). */
export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** "Oct 14, 2026" for a calendar date like "2026-10-14". */
export function formatDate(day: string): string {
  return calendarDate.format(new Date(`${day}T00:00:00Z`));
}

/** "Oct 14, 2026 – Oct 20, 2026", or a single date if both are the same day. */
export function formatRange(start: string, end: string): string {
  return start === end ? formatDate(start) : `${formatDate(start)} – ${formatDate(end)}`;
}

/** Yesterday's date in New York, as YYYY-MM-DD: the latest day a run can cover. */
export function yesterdayInNewYork(now: Date = new Date()): string {
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: TIMEZONE }).format(now); // YYYY-MM-DD
  const date = new Date(`${today}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

/** Who started a run, in words. */
export function startedBy(trigger: string, triggeredBy: string): string {
  return trigger === "scheduled" ? "Daily schedule" : triggeredBy;
}
