// Korea has no daylight saving time, so KST is always UTC+9.
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

/** "YYYY-MM-DD" of the given instant in Korea time. */
export function kstDateKey(date: Date): string {
  return new Date(date.getTime() + KST_OFFSET_MS).toISOString().slice(0, 10);
}

/** Hour 0-23 of the given instant in Korea time. */
export function kstHour(date: Date): number {
  return new Date(date.getTime() + KST_OFFSET_MS).getUTCHours();
}

/** [start, end) of a Korean calendar day as UTC instants. */
export function kstDayRange(dateKey: string): { start: Date; end: Date } {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) throw new Error(`invalid date ${dateKey}`);
  const start = new Date(`${dateKey}T00:00:00+09:00`);
  return { start, end: new Date(start.getTime() + 24 * 60 * 60 * 1000) };
}

export function minutesBetween(a: Date, b: Date): number {
  return Math.max(0, Math.round((b.getTime() - a.getTime()) / 60000));
}
