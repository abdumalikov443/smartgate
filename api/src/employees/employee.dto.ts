import { ArrayMaxSize, ArrayMinSize, Equals, IsArray, IsNumber, IsOptional, IsString, MaxLength, MinLength } from 'class-validator';

export class CreateEmployeeDto {
  @IsString() @MinLength(1) @MaxLength(80) name: string;
  @IsOptional() @IsString() @MaxLength(80) department?: string;
  /** The person must agree to biometric processing before anything is stored. */
  @Equals(true, { message: 'consent must be true - face data needs the employee\'s agreement' }) consent: boolean;
}

export class EnrollFaceDto {
  @IsArray() @ArrayMinSize(512) @ArrayMaxSize(512) @IsNumber({}, { each: true }) embedding: number[];
}
