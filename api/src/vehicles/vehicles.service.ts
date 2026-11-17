import { Injectable } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { Model } from 'mongoose';
import { SnapshotStore } from '../common/snapshots';
import { kstDateKey, kstDayRange } from '../common/time';
import { EventsGateway } from '../realtime/events.gateway';
import { VehicleEventDto } from './vehicle-event.dto';
import { buildVehicleStats, chooseVisitToClose, dwellMinutes, STALE_VISIT_HOURS } from './vehicle-logic';
import { VehicleEvent, VehicleVisit } from './vehicle.schemas';

@Injectable()
export class VehiclesService {
  constructor(
    @InjectModel(VehicleEvent.name) private readonly events: Model<VehicleEvent>,
    @InjectModel(VehicleVisit.name) private readonly visits: Model<VehicleVisit>,
    private readonly snapshots: SnapshotStore,
    private readonly gateway: EventsGateway,
  ) {}

  async record(dto: VehicleEventDto) {
    const occurredAt = new Date(dto.occurredAt);
    const event = await this.events.create({
      gateId: dto.gateId, trackId: dto.trackId, vehicleType: dto.vehicleType, direction: dto.direction,
      plate: dto.plate ?? null, plateConfidence: dto.plateConfidence ?? 0, occurredAt,
      snapshotUrl: await this.snapshots.save(dto.snapshot, occurredAt),
    });

    let visit = null;
    if (dto.direction === 'IN') {
      visit = await this.visits.create({
        plate: event.plate, vehicleType: event.vehicleType, gateId: event.gateId, inAt: occurredAt, inEventId: event._id,
      });
    } else {
      const candidates = await this.visits
        .find({ outAt: null, inAt: { $gte: new Date(occurredAt.getTime() - 7 * 24 * 3600_000), $lte: occurredAt } })
        .lean();
      const match = chooseVisitToClose(candidates, { ...event.toObject(), occurredAt });
      if (match) {
        visit = await this.visits.findOneAndUpdate(
          { _id: match._id, outAt: null },                          // atomic: never close a visit twice
          { outAt: occurredAt, outEventId: event._id, dwellMinutes: dwellMinutes(match.inAt, occurredAt) },
          { new: true },
        );
      }
    }
    const payload = { event: event.toObject(), visit };
    this.gateway.emit('vehicle', payload);
    return payload;
  }

  async recent(limit = 30) {
    return this.events.find().sort({ occurredAt: -1 }).limit(Math.min(limit, 200)).lean();
  }

  async insideNow() {
    const since = new Date(Date.now() - STALE_VISIT_HOURS * 3600_000);
    return this.visits.find({ outAt: null, inAt: { $gte: since } }).sort({ inAt: 1 }).lean();
  }

  async stats(dateKey = kstDateKey(new Date())) {
    const { start, end } = kstDayRange(dateKey);
    const [events, open, closed] = await Promise.all([
      this.events.find({ occurredAt: { $gte: start, $lt: end } }, { snapshotUrl: 0 }).lean(),
      this.visits.find({ outAt: null }).lean(),
      this.visits.find({ outAt: { $gte: start, $lt: end } }).lean(),
    ]);
    return { date: dateKey, ...buildVehicleStats(events, open, closed, new Date()) };
  }
}
