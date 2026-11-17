import { Module } from '@nestjs/common';
import { MongooseModule } from '@nestjs/mongoose';
import { SnapshotStore } from '../common/snapshots';
import { RealtimeModule } from '../realtime/realtime.module';
import { VehicleEvent, VehicleEventSchema, VehicleVisit, VehicleVisitSchema } from './vehicle.schemas';
import { VehiclesController } from './vehicles.controller';
import { VehiclesService } from './vehicles.service';

@Module({
  imports: [
    MongooseModule.forFeature([
      { name: VehicleEvent.name, schema: VehicleEventSchema },
      { name: VehicleVisit.name, schema: VehicleVisitSchema },
    ]),
    RealtimeModule,
  ],
  controllers: [VehiclesController],
  providers: [VehiclesService, SnapshotStore],
})
export class VehiclesModule {}
