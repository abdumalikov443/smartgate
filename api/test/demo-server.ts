// Starts the API with in-memory fake services (no MongoDB) to preview the dashboard.
//   npx ts-node test/demo-server.ts      -> http://localhost:3100
import { NestExpressApplication } from '@nestjs/platform-express';
import { Test } from '@nestjs/testing';
import { AttendanceController } from '../src/attendance/attendance.controller';
import { summarizeAttendance } from '../src/attendance/attendance-logic';
import { AttendanceService } from '../src/attendance/attendance.service';
import { EmployeesController } from '../src/employees/employees.controller';
import { EmployeesService } from '../src/employees/employees.service';
import { configure } from '../src/main';
import { EventsGateway } from '../src/realtime/events.gateway';
import { buildVehicleStats } from '../src/vehicles/vehicle-logic';
import { VehiclesController } from '../src/vehicles/vehicles.controller';
import { VehiclesService } from '../src/vehicles/vehicles.service';

const day = new Date(new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10) + 'T00:00:00+09:00');
const at = (h: number, m: number) => new Date(day.getTime() + (h * 60 + m) * 60000);
let seed = 3;
const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
const types = ['car', 'car', 'car', 'truck', 'truck', 'bus', 'motorcycle'] as const;
const letters = '가나다라마거너더러머고노도로모구누두루무바사아자배하허호';
const events: any[] = [];
const visits: any[] = [];
for (let i = 0; i < 90; i++) {
  const h = 6 + Math.floor(rnd() * 12), m = Math.floor(rnd() * 60);
  const vt = types[Math.floor(rnd() * types.length)];
  const plate = rnd() < 0.85 ? `${10 + Math.floor(rnd() * 380)}${letters[Math.floor(rnd() * letters.length)]}${1000 + Math.floor(rnd() * 8999)}` : null;
  const inAt = at(h, m);
  const stay = vt === 'truck' ? 20 + rnd() * 200 : 10 + rnd() * 400;
  const outAt = rnd() < 0.8 ? new Date(inAt.getTime() + stay * 60000) : null;
  events.push({ vehicleType: vt, direction: 'IN', occurredAt: inAt, plate, snapshotUrl: null });
  if (outAt && outAt < at(19, 0)) events.push({ vehicleType: vt, direction: 'OUT', occurredAt: outAt, plate, snapshotUrl: null });
  visits.push({ vehicleType: vt, plate, inAt, outAt: outAt && outAt < at(19, 0) ? outAt : null, dwellMinutes: outAt && outAt < at(19, 0) ? Math.round(stay) : null });
}
events.sort((a, b) => b.occurredAt - a.occurredAt);
const people = ['Asadbek Abdumalikov', 'Kim Seoyeon', 'Pak Do-Yun', 'Sofia Morgan', 'Ali Karimov'];

async function main() {
  const moduleRef = await Test.createTestingModule({
    controllers: [VehiclesController, EmployeesController, AttendanceController],
    providers: [
      EventsGateway,
      { provide: VehiclesService, useValue: {
        recent: async () => events.slice(0, 40),
        insideNow: async () => visits.filter((v) => !v.outAt).sort((a, b) => a.inAt - b.inAt),
        stats: async () => ({ date: '', ...buildVehicleStats(events, visits.filter((v) => !v.outAt), visits.filter((v) => v.outAt), at(19, 0)) }),
      } },
      { provide: EmployeesService, useValue: { list: async () => people.map((name, i) => ({ id: String(i), name, enrolled: true })) } },
      { provide: AttendanceService, useValue: {
        day: async () => ({ rows: summarizeAttendance(people.map((name, i) => ({
          employeeId: String(i), name, date: '', firstSeen: at(8, 40 + i * 9), lastSeen: at(17 + (i % 2), 50 - i * 7), sightings: i === 4 ? 1 : 6,
        }))) }),
        recentAlerts: async () => [{ cameraId: 'entrance', occurredAt: at(13, 12), similarity: 0.18 }, { cameraId: 'entrance', occurredAt: at(10, 4), similarity: 0.22 }],
      } },
    ],
  }).compile();
  const app = configure(moduleRef.createNestApplication<NestExpressApplication>());
  await app.listen(3100);
  console.log('demo dashboard on http://localhost:3100');
}
main();
