import { BadRequestException, Body, Controller, Get, Post, Query, UseGuards } from '@nestjs/common';
import { ApiKeyGuard } from '../common/api-key.guard';
import { VehicleEventDto } from './vehicle-event.dto';
import { VehiclesService } from './vehicles.service';

@Controller()
export class VehiclesController {
  constructor(private readonly vehicles: VehiclesService) {}

  @Post('vehicle-events')
  @UseGuards(ApiKeyGuard)
  record(@Body() dto: VehicleEventDto) {
    return this.vehicles.record(dto);
  }

  @Get('vehicle-events')
  recent(@Query('limit') limit?: string) {
    return this.vehicles.recent(limit ? Number(limit) : 30);
  }

  @Get('vehicles/inside')
  inside() {
    return this.vehicles.insideNow();
  }

  @Get('stats/vehicles')
  stats(@Query('date') date?: string) {
    if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) throw new BadRequestException('date must be YYYY-MM-DD');
    return this.vehicles.stats(date);
  }
}
