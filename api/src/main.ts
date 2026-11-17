import { Logger, ValidationPipe } from '@nestjs/common';
import { NestFactory } from '@nestjs/core';
import { NestExpressApplication } from '@nestjs/platform-express';
import { join } from 'path';
import { AppModule } from './app.module';
import { UPLOAD_DIR } from './common/snapshots';

export function configure(app: NestExpressApplication) {
  app.setGlobalPrefix('api');
  app.enableCors();
  app.useBodyParser('json', { limit: '2mb' });                 // snapshots are sent as base64
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
  app.useStaticAssets(UPLOAD_DIR, { prefix: '/uploads' });
  // Chart.js is served locally so the dashboard also works on an offline factory LAN
  app.useStaticAssets(join(require.resolve('chart.js'), '..', '..', 'dist'), { prefix: '/vendor/chartjs' });
  app.useStaticAssets(join(__dirname, '..', 'public'));        // dashboard
  return app;
}

async function bootstrap() {
  const app = configure(await NestFactory.create<NestExpressApplication>(AppModule));
  if (!process.env.WORKER_API_KEY) Logger.warn('WORKER_API_KEY is not set - the worker cannot send events', 'SmartGate');
  const port = Number(process.env.PORT ?? 3000);
  await app.listen(port);
  Logger.log(`Dashboard: http://localhost:${port}`, 'SmartGate');
}

if (require.main === module) bootstrap();
