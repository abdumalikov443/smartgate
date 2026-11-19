// HTTP layer tests: routing, API-key guard and request validation.
// Services are replaced with fakes, so no MongoDB is needed.
import { INestApplication } from '@nestjs/common';
import { NestExpressApplication } from '@nestjs/platform-express';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AttendanceController } from '../src/attendance/attendance.controller';
import { AttendanceService } from '../src/attendance/attendance.service';
import { EmployeesController } from '../src/employees/employees.controller';
import { EmployeesService } from '../src/employees/employees.service';
import { configure } from '../src/main';
import { VehiclesController } from '../src/vehicles/vehicles.controller';
import { VehiclesService } from '../src/vehicles/vehicles.service';

const KEY = 'test-key-123';
const vehicleEvent = {
  gateId: 'main', trackId: 4, vehicleType: 'truck', direction: 'IN',
  plate: '12가3456', plateConfidence: 0.91, occurredAt: '2026-11-17T01:00:00Z',
};

describe('SmartGate HTTP API', () => {
  let app: INestApplication;
  const vehicles = { record: jest.fn(async (d) => ({ event: d })), recent: jest.fn(async () => []), insideNow: jest.fn(async () => []), stats: jest.fn(async (d) => ({ date: d })) };
  const employees = { list: jest.fn(async () => []), create: jest.fn(async (d) => ({ id: '1', ...d })), embeddings: jest.fn(async () => []), enroll: jest.fn(async () => ({})), removeFace: jest.fn(async () => ({})), remove: jest.fn(async () => ({})) };
  const attendance = { record: jest.fn(async () => ({})), day: jest.fn(async () => ({ rows: [] })), recentAlerts: jest.fn(async () => []) };

  beforeAll(async () => {
    process.env.WORKER_API_KEY = KEY;
    const moduleRef = await Test.createTestingModule({
      controllers: [VehiclesController, EmployeesController, AttendanceController],
      providers: [
        { provide: VehiclesService, useValue: vehicles },
        { provide: EmployeesService, useValue: employees },
        { provide: AttendanceService, useValue: attendance },
      ],
    }).compile();
    app = configure(moduleRef.createNestApplication<NestExpressApplication>());
    await app.init();
  });
  afterAll(() => app.close());
  beforeEach(() => jest.clearAllMocks());

  const post = (url: string, body: object, key: string | null = KEY) => {
    const r = request(app.getHttpServer()).post(url).send(body);
    return key ? r.set('x-api-key', key) : r;
  };

  it('accepts a valid vehicle event with the key', async () => {
    await post('/api/vehicle-events', vehicleEvent).expect(201);
    expect(vehicles.record).toHaveBeenCalledWith(expect.objectContaining({ plate: '12가3456', direction: 'IN' }));
  });

  it('rejects events without or with a wrong API key', async () => {
    await post('/api/vehicle-events', vehicleEvent, null).expect(401);
    await post('/api/vehicle-events', vehicleEvent, 'wrong-key-123').expect(401);
    expect(vehicles.record).not.toHaveBeenCalled();
  });

  it('validates vehicle events', async () => {
    await post('/api/vehicle-events', { ...vehicleEvent, vehicleType: 'tank' }).expect(400);
    await post('/api/vehicle-events', { ...vehicleEvent, direction: 'UP' }).expect(400);
    await post('/api/vehicle-events', { ...vehicleEvent, plate: 'ABC-123' }).expect(400);
    await post('/api/vehicle-events', { ...vehicleEvent, extra: 1 }).expect(400);
    await post('/api/vehicle-events', { ...vehicleEvent, plate: null }).expect(201);   // unreadable plate is fine
    await post('/api/vehicle-events', { ...vehicleEvent, plate: null, plateDigits: '2641' }).expect(201);
    await post('/api/vehicle-events', { ...vehicleEvent, plateDigits: '26a1' }).expect(400);
  });

  it('serves stats and checks the date format', async () => {
    await request(app.getHttpServer()).get('/api/stats/vehicles?date=2026-11-17').expect(200);
    expect(vehicles.stats).toHaveBeenCalledWith('2026-11-17');
    await request(app.getHttpServer()).get('/api/stats/vehicles?date=yesterday').expect(400);
  });

  it('requires consent to create an employee', async () => {
    await post('/api/employees', { name: 'Asadbek', consent: false }).expect(400);
    await post('/api/employees', { name: 'Asadbek', department: 'IT', consent: true }).expect(201);
  });

  it('accepts only 512-number face embeddings', async () => {
    await post('/api/employees/abc/face', { embedding: [0.1, 0.2] }).expect(400);
    await post('/api/employees/abc/face', { embedding: Array(512).fill(0.01) }).expect(201);
  });

  it('keeps embeddings behind the API key', async () => {
    await request(app.getHttpServer()).get('/api/employees/embeddings').expect(401);
    await request(app.getHttpServer()).get('/api/employees/embeddings').set('x-api-key', KEY).expect(200);
  });

  it('validates face events', async () => {
    await post('/api/face-events', { cameraId: 'entrance', employeeId: 'not-an-id', similarity: 0.6, occurredAt: '2026-11-17T00:00:00Z' }).expect(400);
    await post('/api/face-events', { cameraId: 'entrance', employeeId: null, similarity: 0.2, occurredAt: '2026-11-17T00:00:00Z' }).expect(201);
  });
});
