// Pure business rules for the gate log - no database, so they are unit-tested directly.
import { kstHour, minutesBetween } from '../common/time';
import { Direction, VEHICLE_TYPES, VehicleType } from './vehicle.schemas';

export interface EventLike { vehicleType: VehicleType; direction: Direction; occurredAt: Date; plate?: string | null }
export interface VisitLike { _id?: unknown; plate?: string | null; vehicleType: VehicleType; inAt: Date; outAt?: Date | null; dwellMinutes?: number | null }

/** A visit still open after this long is treated as a missed OUT, not "inside now". */
export const STALE_VISIT_HOURS = 24;

/**
 * Which open visit does an OUT event close?
 * - with a plate: the latest open visit with the same plate (exact match);
 * - without a plate: the oldest open plate-less visit of the same vehicle type (FIFO estimate).
 */
export function chooseVisitToClose<T extends VisitLike>(open: T[], out: EventLike): T | null {
  const before = open.filter((v) => !v.outAt && v.inAt.getTime() <= out.occurredAt.getTime());
  if (out.plate) {
    const same = before.filter((v) => v.plate === out.plate);
    return same.sort((a, b) => b.inAt.getTime() - a.inAt.getTime())[0] ?? null;
  }
  const unplated = before.filter((v) => !v.plate && v.vehicleType === out.vehicleType);
  return unplated.sort((a, b) => a.inAt.getTime() - b.inAt.getTime())[0] ?? null;
}

export function dwellMinutes(inAt: Date, outAt: Date): number {
  return minutesBetween(inAt, outAt);
}

export interface VehicleStats {
  totals: Record<Direction, number>;
  byType: Record<VehicleType, Record<Direction, number>>;
  hourly: { hour: number; IN: number; OUT: number }[];
  insideNow: number;
  insideByType: Record<VehicleType, number>;
  avgDwellMinutes: number | null;
  avgDwellByType: Record<VehicleType, number | null>;
  platesRead: number;
  plateReadRate: number | null;
}

/** Dashboard numbers for one day. `openVisits` = visits without OUT; `closedVisits` = closed that day. */
export function buildVehicleStats(events: EventLike[], openVisits: VisitLike[], closedVisits: VisitLike[], now: Date): VehicleStats {
  const zero = () => Object.fromEntries(VEHICLE_TYPES.map((t) => [t, { IN: 0, OUT: 0 }])) as VehicleStats['byType'];
  const byType = zero();
  const hourly = Array.from({ length: 24 }, (_, hour) => ({ hour, IN: 0, OUT: 0 }));
  const totals = { IN: 0, OUT: 0 };
  for (const e of events) {
    totals[e.direction] += 1;
    byType[e.vehicleType][e.direction] += 1;
    hourly[kstHour(e.occurredAt)][e.direction] += 1;
  }
  const staleBefore = now.getTime() - STALE_VISIT_HOURS * 3600_000;
  const inside = openVisits.filter((v) => !v.outAt && v.inAt.getTime() >= staleBefore);
  const insideByType = Object.fromEntries(VEHICLE_TYPES.map((t) => [t, inside.filter((v) => v.vehicleType === t).length])) as VehicleStats['insideByType'];
  const avg = (xs: number[]) => (xs.length ? Math.round(xs.reduce((a, b) => a + b, 0) / xs.length) : null);
  const dwell = (vs: VisitLike[]) => vs.map((v) => v.dwellMinutes).filter((m): m is number => typeof m === 'number');
  const platesRead = events.filter((e) => e.plate).length;
  return {
    totals, byType, hourly,
    insideNow: inside.length, insideByType,
    avgDwellMinutes: avg(dwell(closedVisits)),
    avgDwellByType: Object.fromEntries(VEHICLE_TYPES.map((t) => [t, avg(dwell(closedVisits.filter((v) => v.vehicleType === t)))])) as VehicleStats['avgDwellByType'],
    platesRead,
    plateReadRate: events.length ? Math.round((platesRead / events.length) * 1000) / 1000 : null,
  };
}
