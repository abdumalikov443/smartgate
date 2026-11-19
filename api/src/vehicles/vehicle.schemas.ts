import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument, Types } from 'mongoose';

export const VEHICLE_TYPES = ['car', 'truck', 'bus', 'motorcycle'] as const;
export type VehicleType = (typeof VEHICLE_TYPES)[number];
export type Direction = 'IN' | 'OUT';

/** One crossing of the gate line, as reported by the AI worker. */
@Schema({ timestamps: true, collection: 'vehicleEvents' })
export class VehicleEvent {
  @Prop({ required: true }) gateId: string;
  @Prop() trackId?: number;
  @Prop({ required: true, enum: VEHICLE_TYPES }) vehicleType: VehicleType;
  @Prop({ required: true, enum: ['IN', 'OUT'] }) direction: Direction;
  @Prop({ type: String, default: null, index: true }) plate: string | null;
  @Prop({ type: String, default: null }) plateDigits: string | null;
  @Prop({ default: 0 }) plateConfidence: number;
  @Prop({ required: true, index: true }) occurredAt: Date;
  @Prop({ type: String, default: null }) snapshotUrl: string | null;
}
export type VehicleEventDocument = HydratedDocument<VehicleEvent>;
export const VehicleEventSchema = SchemaFactory.createForClass(VehicleEvent);

/** An IN event paired with its OUT event: how long a vehicle stayed inside. */
@Schema({ timestamps: true, collection: 'vehicleVisits' })
export class VehicleVisit {
  @Prop({ type: String, default: null, index: true }) plate: string | null;
  @Prop({ type: String, default: null, index: true }) plateDigits: string | null;
  @Prop({ required: true, enum: VEHICLE_TYPES }) vehicleType: VehicleType;
  @Prop({ required: true }) gateId: string;
  @Prop({ required: true, index: true }) inAt: Date;
  @Prop({ type: Date, default: null, index: true }) outAt: Date | null;
  @Prop({ type: Number, default: null }) dwellMinutes: number | null;
  @Prop({ type: Types.ObjectId, ref: 'VehicleEvent' }) inEventId: Types.ObjectId;
  @Prop({ type: Types.ObjectId, ref: 'VehicleEvent', default: null }) outEventId: Types.ObjectId | null;
}
export type VehicleVisitDocument = HydratedDocument<VehicleVisit>;
export const VehicleVisitSchema = SchemaFactory.createForClass(VehicleVisit);
VehicleVisitSchema.index({ outAt: 1, inAt: 1 });
