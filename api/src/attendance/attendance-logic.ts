import { minutesBetween } from '../common/time';

export interface AttendanceRow { employeeId: string; name: string; date: string; firstSeen: Date; lastSeen: Date; sightings: number }

/** Work time = first to last sighting. A single sighting means "checked in, not yet out". */
export function summarizeAttendance(rows: AttendanceRow[], lateAfter = '09:30') {
  const [lh, lm] = lateAfter.split(':').map(Number);
  return rows
    .map((r) => {
      const kst = new Date(r.firstSeen.getTime() + 9 * 3600_000);
      const late = kst.getUTCHours() * 60 + kst.getUTCMinutes() > lh * 60 + lm;
      return {
        ...r,
        workMinutes: r.sightings > 1 ? minutesBetween(r.firstSeen, r.lastSeen) : 0,
        status: r.sightings > 1 ? 'present' : 'checked_in',
        late,
      };
    })
    .sort((a, b) => a.firstSeen.getTime() - b.firstSeen.getTime());
}
