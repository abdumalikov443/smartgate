import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';
import { timingSafeEqual } from 'crypto';

/** Write endpoints are called by the AI worker and admin scripts with a shared key. */
@Injectable()
export class ApiKeyGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const expected = process.env.WORKER_API_KEY ?? '';
    const given = String(context.switchToHttp().getRequest().headers['x-api-key'] ?? '');
    const ok = expected.length > 0 && given.length === expected.length &&
      timingSafeEqual(Buffer.from(given), Buffer.from(expected));
    if (!ok) throw new UnauthorizedException('Invalid or missing x-api-key');
    return true;
  }
}
