import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { MongooseModule } from '@nestjs/mongoose';
import { AttendanceModule } from './attendance/attendance.module';
import { EmployeesModule } from './employees/employees.module';
import { RealtimeModule } from './realtime/realtime.module';
import { VehiclesModule } from './vehicles/vehicles.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),
    MongooseModule.forRootAsync({
      useFactory: () => ({ uri: process.env.MONGO_URI ?? 'mongodb://127.0.0.1:27017/smartgate' }),
    }),
    RealtimeModule,
    VehiclesModule,
    EmployeesModule,
    AttendanceModule,
  ],
})
export class AppModule {}
