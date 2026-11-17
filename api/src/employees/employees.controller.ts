import { Body, Controller, Delete, Get, Param, Post, UseGuards } from '@nestjs/common';
import { ApiKeyGuard } from '../common/api-key.guard';
import { CreateEmployeeDto, EnrollFaceDto } from './employee.dto';
import { EmployeesService } from './employees.service';

@Controller('employees')
export class EmployeesController {
  constructor(private readonly employees: EmployeesService) {}

  @Get()
  list() {
    return this.employees.list();
  }

  @Post()
  @UseGuards(ApiKeyGuard)
  create(@Body() dto: CreateEmployeeDto) {
    return this.employees.create(dto);
  }

  @Get('embeddings')
  @UseGuards(ApiKeyGuard)
  embeddings() {
    return this.employees.embeddings();
  }

  @Post(':id/face')
  @UseGuards(ApiKeyGuard)
  enroll(@Param('id') id: string, @Body() dto: EnrollFaceDto) {
    return this.employees.enroll(id, dto.embedding);
  }

  @Delete(':id/face')
  @UseGuards(ApiKeyGuard)
  removeFace(@Param('id') id: string) {
    return this.employees.removeFace(id);
  }

  @Delete(':id')
  @UseGuards(ApiKeyGuard)
  remove(@Param('id') id: string) {
    return this.employees.remove(id);
  }
}
