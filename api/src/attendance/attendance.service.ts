import { BadRequestException, Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model, Types } from 'mongoose';
import { SnapshotStore } from '../common/snapshots';
import { kstDateKey } from '../common/time';
import { EmployeesService } from '../employees/employees.service';
import { EventsGateway } from '../realtime/events.gateway';
import { summarizeAttendance } from './attendance-logic';
import { Alert, Attendance } from './attendance.schemas';
import { FaceEventDto } from './face-event.dto';

@Injectable()
export class AttendanceService {
  constructor(
    @InjectModel(Attendance.name) private readonly attendance: Model<Attendance>,
    @InjectModel(Alert.name) private readonly alerts: Model<Alert>,
    private readonly employees: EmployeesService,
    private readonly snapshots: SnapshotStore,
    private readonly gateway: EventsGateway,
  ) {}

  async record(dto: FaceEventDto) {
    const at = new Date(dto.occurredAt);
    if (!dto.employeeId) {
      const alert = await this.alerts.create({
        type: 'unknown_person', cameraId: dto.cameraId, similarity: dto.similarity, occurredAt: at,
        snapshotUrl: await this.snapshots.save(dto.snapshot, at),
      });
      this.gateway.emit('alert', alert.toObject());
      return { alert };
    }
    if (!(await this.employees.exists(dto.employeeId))) throw new BadRequestException('unknown employeeId');
    // atomic upsert: earliest sighting = check-in, latest = check-out
    const row = await this.attendance.findOneAndUpdate(
      { employeeId: new Types.ObjectId(dto.employeeId), date: kstDateKey(at) },
      { $min: { firstSeen: at }, $max: { lastSeen: at }, $inc: { sightings: 1 } },
      { upsert: true, new: true },
    ).lean();
    this.gateway.emit('attendance', row);
    return { attendance: row };
  }

  async day(dateKey = kstDateKey(new Date())) {
    const rows = await this.attendance.find({ date: dateKey }).lean();
    const names = await this.employees.namesById(rows.map((r) => String(r.employeeId)));
    return {
      date: dateKey,
      rows: summarizeAttendance(rows.map((r) => ({
        employeeId: String(r.employeeId), name: names.get(String(r.employeeId)) ?? '(deleted)',
        date: r.date, firstSeen: r.firstSeen, lastSeen: r.lastSeen, sightings: r.sightings,
      }))),
    };
  }

  async recentAlerts(limit = 20) {
    return this.alerts.find().sort({ occurredAt: -1 }).limit(Math.min(limit, 100)).lean();
  }
}
