import { BadRequestException, Body, Controller, Get, Post, Query, UseGuards } from '@nestjs/common';
import { ApiKeyGuard } from '../common/api-key.guard';
import { AttendanceService } from './attendance.service';
import { FaceEventDto } from './face-event.dto';

@Controller()
export class AttendanceController {
  constructor(private readonly attendance: AttendanceService) {}

  @Post('face-events')
  @UseGuards(ApiKeyGuard)
  record(@Body() dto: FaceEventDto) {
    return this.attendance.record(dto);
  }

  @Get('attendance')
  day(@Query('date') date?: string) {
    if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new BadRequestException('date must be YYYY-MM-DD');
    return this.attendance.day(date);
  }

  @Get('alerts')
  alerts(@Query('limit') limit?: string) {
    return this.attendance.recentAlerts(limit ? Number(limit) : 20);
  }
}
