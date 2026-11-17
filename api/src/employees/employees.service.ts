import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectModel } from '@nestjs/mongoose';
import { isValidObjectId, Model } from 'mongoose';
import { CreateEmployeeDto } from './employee.dto';
import { Employee } from './employee.schema';

export const publicEmployee = (e: any) => ({
  id: String(e._id), name: e.name, department: e.department, consentAt: e.consentAt,
  enrolled: Boolean(e.enrolledAt), enrolledAt: e.enrolledAt,
});

@Injectable()
export class EmployeesService {
  constructor(@InjectModel(Employee.name) private readonly employees: Model<Employee>) {}

  async create(dto: CreateEmployeeDto) {
    const e = await this.employees.create({ name: dto.name, department: dto.department ?? '', consentAt: new Date() });
    return publicEmployee(e);
  }

  async list() {
    return (await this.employees.find().sort({ name: 1 }).lean()).map(publicEmployee);
  }

  async namesById(ids: string[]): Promise<Map<string, string>> {
    const rows = await this.employees.find({ _id: { $in: ids.filter(isValidObjectId) } }, { name: 1 }).lean();
    return new Map(rows.map((r) => [String(r._id), r.name]));
  }

  async exists(id: string): Promise<boolean> {
    return isValidObjectId(id) && (await this.employees.exists({ _id: id })) !== null;
  }

  async enroll(id: string, embedding: number[]) {
    const norm = Math.hypot(...embedding) || 1;
    const e = await this.findOr404(id);
    e.faceEmbedding = embedding.map((v) => v / norm);
    e.enrolledAt = new Date();
    await e.save();
    return publicEmployee(e);
  }

  /** Right to be forgotten: delete the biometric template, keep the attendance history. */
  async removeFace(id: string) {
    const e = await this.findOr404(id);
    e.faceEmbedding = undefined;
    e.enrolledAt = null;
    await e.save();
    return publicEmployee(e);
  }

  async remove(id: string) {
    const e = await this.findOr404(id);
    await e.deleteOne();
    return { deleted: true };
  }

  /** Templates for the AI worker only (guarded endpoint). */
  async embeddings() {
    const rows = await this.employees.find({ enrolledAt: { $ne: null } }).select('+faceEmbedding').lean();
    return rows.map((r) => ({ id: String(r._id), name: r.name, embedding: r.faceEmbedding }));
  }

  private async findOr404(id: string) {
    const e = isValidObjectId(id) ? await this.employees.findById(id) : null;
    if (!e) throw new NotFoundException('employee not found');
    return e;
  }
}
