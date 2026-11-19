import { summarizeAttendance } from '../src/attendance/attendance-logic';
import { kstDateKey, kstDayRange, kstHour, minutesBetween } from '../src/common/time';
import { buildVehicleStats, chooseVisitToClose, VisitLike } from '../src/vehicles/vehicle-logic';

const t = (iso: string) => new Date(iso);

describe('Korea time helpers', () => {
  it('uses UTC+9 for day keys and hours', () => {
    expect(kstDateKey(t('2026-11-17T15:30:00Z'))).toBe('2026-11-18');   // 00:30 KST next day
    expect(kstHour(t('2026-11-17T00:10:00Z'))).toBe(9);
    const { start, end } = kstDayRange('2026-11-18');
    expect(start.toISOString()).toBe('2026-11-17T15:00:00.000Z');
    expect(end.getTime() - start.getTime()).toBe(86_400_000);
    expect(minutesBetween(t('2026-11-17T01:00:00Z'), t('2026-11-17T02:30:00Z'))).toBe(90);
    expect(() => kstDayRange('17-11-2026')).toThrow();
  });
});

describe('chooseVisitToClose', () => {
  const open: VisitLike[] = [
    { _id: 'a', plate: '12가3456', vehicleType: 'truck', inAt: t('2026-11-17T00:00:00Z') },
    { _id: 'b', plate: '12가3456', vehicleType: 'truck', inAt: t('2026-11-17T02:00:00Z') },
    { _id: 'c', plate: null, vehicleType: 'car', inAt: t('2026-11-17T01:00:00Z') },
    { _id: 'd', plate: null, vehicleType: 'car', inAt: t('2026-11-17T00:30:00Z') },
    { _id: 'e', plate: null, vehicleType: 'truck', inAt: t('2026-11-17T00:15:00Z') },
  ];

  it('matches the latest open visit with the same plate', () => {
    const v = chooseVisitToClose(open, { plate: '12가3456', vehicleType: 'truck', direction: 'OUT', occurredAt: t('2026-11-17T03:00:00Z') });
    expect(v?._id).toBe('b');
  });

  it('ignores visits that started after the OUT event', () => {
    const v = chooseVisitToClose(open, { plate: '12가3456', vehicleType: 'truck', direction: 'OUT', occurredAt: t('2026-11-17T01:00:00Z') });
    expect(v?._id).toBe('a');
  });

  it('without a plate closes the oldest plate-less visit of the same type', () => {
    const v = chooseVisitToClose(open, { plate: null, vehicleType: 'car', direction: 'OUT', occurredAt: t('2026-11-17T05:00:00Z') });
    expect(v?._id).toBe('d');
  });

  it('matches by the last 4 digits when the plate letter was unreadable', () => {
    const visits: VisitLike[] = [
      { _id: 'x', plateDigits: '2641', vehicleType: 'car', inAt: t('2026-11-17T01:00:00Z') },
      { _id: 'y', plate: '34배7104', plateDigits: '7104', vehicleType: 'car', inAt: t('2026-11-17T01:10:00Z') },
      { _id: 'z', vehicleType: 'car', inAt: t('2026-11-17T00:50:00Z') },
    ];
    const at = t('2026-11-17T04:00:00Z');
    expect(chooseVisitToClose(visits, { plateDigits: '2641', vehicleType: 'car', direction: 'OUT', occurredAt: at })?._id).toBe('x');
    // full plate on OUT, only digits on IN
    expect(chooseVisitToClose(visits, { plate: '32배2641', vehicleType: 'car', direction: 'OUT', occurredAt: at })?._id).toBe('x');
    // digits-only OUT can also close a visit whose IN had the full plate
    expect(chooseVisitToClose(visits, { plateDigits: '7104', vehicleType: 'car', direction: 'OUT', occurredAt: at })?._id).toBe('y');
    // a full plate that matches nothing must not close a random visit
    expect(chooseVisitToClose(visits, { plate: '99허9999', vehicleType: 'car', direction: 'OUT', occurredAt: at })).toBeNull();
    // nothing readable: FIFO only among visits without any plate info
    expect(chooseVisitToClose(visits, { vehicleType: 'car', direction: 'OUT', occurredAt: at })?._id).toBe('z');
  });

  it('returns null when nothing matches', () => {
    expect(chooseVisitToClose(open, { plate: '99허9999', vehicleType: 'car', direction: 'OUT', occurredAt: t('2026-11-17T05:00:00Z') })).toBeNull();
    expect(chooseVisitToClose(open, { plate: null, vehicleType: 'bus', direction: 'OUT', occurredAt: t('2026-11-17T05:00:00Z') })).toBeNull();
  });
});

describe('buildVehicleStats', () => {
  const now = t('2026-11-17T08:00:00Z');                       // 17:00 KST
  const events = [
    { vehicleType: 'car' as const, direction: 'IN' as const, occurredAt: t('2026-11-17T00:05:00Z'), plate: '12가3456' },
    { vehicleType: 'truck' as const, direction: 'IN' as const, occurredAt: t('2026-11-17T00:40:00Z'), plate: null },
    { vehicleType: 'car' as const, direction: 'OUT' as const, occurredAt: t('2026-11-17T03:10:00Z'), plate: '12가3456' },
  ];
  const open: VisitLike[] = [
    { vehicleType: 'truck', inAt: t('2026-11-17T00:40:00Z') },
    { vehicleType: 'car', inAt: t('2026-11-15T00:00:00Z') },     // stale: missed OUT 2 days ago
  ];
  const closed: VisitLike[] = [
    { vehicleType: 'car', inAt: t('2026-11-17T00:05:00Z'), outAt: t('2026-11-17T03:10:00Z'), dwellMinutes: 185 },
    { vehicleType: 'truck', inAt: t('2026-11-17T01:00:00Z'), outAt: t('2026-11-17T02:00:00Z'), dwellMinutes: 60 },
  ];
  const s = buildVehicleStats(events, open, closed, now);

  it('counts totals, types and KST hours', () => {
    expect(s.totals).toEqual({ IN: 2, OUT: 1 });
    expect(s.byType.car).toEqual({ IN: 1, OUT: 1 });
    expect(s.hourly[9]).toEqual({ hour: 9, IN: 2, OUT: 0 });
    expect(s.hourly[12].OUT).toBe(1);
  });

  it('excludes stale visits from inside-now and averages dwell', () => {
    expect(s.insideNow).toBe(1);
    expect(s.insideByType.truck).toBe(1);
    expect(s.avgDwellMinutes).toBe(123);
    expect(s.avgDwellByType).toMatchObject({ car: 185, truck: 60, bus: null });
  });

  it('reports the plate read rate', () => {
    expect(s.platesRead).toBe(2);
    expect(s.plateDigitsOnly).toBe(0);
    expect(s.plateReadRate).toBe(0.667);
  });
});

describe('summarizeAttendance', () => {
  it('computes work time, status and lateness in KST', () => {
    const rows = summarizeAttendance([
      { employeeId: '1', name: 'Late', date: '2026-11-17', firstSeen: t('2026-11-17T00:45:00Z'), lastSeen: t('2026-11-17T09:00:00Z'), sightings: 5 },
      { employeeId: '2', name: 'Early', date: '2026-11-17', firstSeen: t('2026-11-16T23:50:00Z'), lastSeen: t('2026-11-16T23:50:00Z'), sightings: 1 },
    ]);
    expect(rows.map((r) => r.name)).toEqual(['Early', 'Late']);
    expect(rows[0]).toMatchObject({ status: 'checked_in', workMinutes: 0, late: false });   // 08:50 KST
    expect(rows[1]).toMatchObject({ status: 'present', workMinutes: 495, late: true });     // 09:45 KST
  });
});
