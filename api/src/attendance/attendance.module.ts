import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { SnapshotStore } from '../common/snapshots';
import { EmployeesModule } from '../employees/employees.module';
import { RealtimeModule } from '../realtime/realtime.module';
import { AttendanceController } from './attendance.controller';
import { Alert, AlertSchema, Attendance, AttendanceSchema } from './attendance.schemas';
import { AttendanceService } from './attendance.service';

@Module({
  imports: [
    MongooseModule.forFeature([
      { name: Attendance.name, schema: AttendanceSchema },
      { name: Alert.name, schema: AlertSchema },
    ]),
    EmployeesModule,
    RealtimeModule,
  ],
  controllers: [AttendanceController],
  providers: [AttendanceService, SnapshotStore],
})
export class AttendanceModule {}
