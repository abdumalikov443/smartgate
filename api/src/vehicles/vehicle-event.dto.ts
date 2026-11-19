import { IsIn, IsInt, IsISO8601, IsNumber, IsOptional, IsString, Matches, Max, MaxLength, Min } from 'class-validator';
import { VEHICLE_TYPES } from './vehicle.schemas';

export const PLATE_PATTERN = /^(서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)?\d{2,3}[가-힣]\d{4}$/;

export class VehicleEventDto {
  @IsString() @MaxLength(50) gateId: string;
  @IsOptional() @IsInt() trackId?: number;
  @IsIn(VEHICLE_TYPES) vehicleType: (typeof VEHICLE_TYPES)[number];
  @IsIn(['IN', 'OUT']) direction: 'IN' | 'OUT';
  @IsOptional() @Matches(PLATE_PATTERN, { message: 'plate must be a Korean plate like 12가3456' }) plate?: string | null;
  /** last 4 digits - sent even when the Hangul letter of the plate could not be read */
  @IsOptional() @Matches(/^\d{4}$/, { message: 'plateDigits must be 4 digits' }) plateDigits?: string | null;
  @IsOptional() @IsNumber() @Min(0) @Max(1) plateConfidence?: number;
  @IsISO8601() occurredAt: string;
  @IsOptional() @IsString() @MaxLength(400_000) snapshot?: string | null;   // base64 JPEG
}
