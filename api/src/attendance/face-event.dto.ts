import { IsISO8601, IsMongoId, IsNumber, IsOptional, IsString, Max, MaxLength, Min } from 'class-validator';

export class FaceEventDto {
  @IsString() @MaxLength(50) cameraId: string;
  /** null / missing = unknown person */
  @IsOptional() @IsMongoId() employeeId?: string | null;
  @IsNumber() @Min(-1) @Max(1) similarity: number;
  @IsISO8601() occurredAt: string;
  @IsOptional() @IsString() @MaxLength(400_000) snapshot?: string | null;
}
