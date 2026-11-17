import { Prop, Schema, SchemaFactory } from '@nestjs/mongoose';
import { HydratedDocument } from 'mongoose';

@Schema({ timestamps: true, collection: 'employees' })
export class Employee {
  @Prop({ required: true, trim: true }) name: string;
  @Prop({ trim: true, default: '' }) department: string;
  /** When the employee agreed to face recognition. Enrolment is refused without it. */
  @Prop({ required: true }) consentAt: Date;
  /** ArcFace template: 512 numbers. Never returned by public endpoints. */
  @Prop({ type: [Number], default: undefined, select: false }) faceEmbedding?: number[];
  @Prop({ type: Date, default: null }) enrolledAt: Date | null;
}
export type EmployeeDocument = HydratedDocument<Employee>;
export const EmployeeSchema = SchemaFactory.createForClass(Employee);
