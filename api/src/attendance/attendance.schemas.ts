import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument, Types } from 'mongoose';

/** One row per employee per Korean calendar day: first and last time they were seen. */
@Schema({ timestamps: true, collection: 'attendance' })
export class Attendance {
  @Prop({ type: Types.ObjectId, ref: 'Employee', required: true }) employeeId: Types.ObjectId;
  @Prop({ required: true }) date: string;            // YYYY-MM-DD in KST
  @Prop({ required: true }) firstSeen: Date;
  @Prop({ required: true }) lastSeen: Date;
  @Prop({ default: 0 }) sightings: number;
}
export type AttendanceDocument = HydratedDocument<Attendance>;
export const AttendanceSchema = SchemaFactory.createForClass(Attendance);
AttendanceSchema.index({ employeeId: 1, date: 1 }, { unique: true });

@Schema({ timestamps: true, collection: 'alerts' })
export class Alert {
  @Prop({ required: true, enum: ['unknown_person'] }) type: 'unknown_person';
  @Prop({ required: true }) cameraId: string;
  @Prop({ default: 0 }) similarity: number;
  @Prop({ required: true, index: true }) occurredAt: Date;
  @Prop({ type: String, default: null }) snapshotUrl: string | null;
}
export type AlertDocument = HydratedDocument<Alert>;
export const AlertSchema = SchemaFactory.createForClass(Alert);
