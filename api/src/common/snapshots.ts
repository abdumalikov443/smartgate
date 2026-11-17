import { Injectable } from '@nestjs/common';
import { randomUUID } from 'crypto';
import { mkdir, writeFile } from 'fs/promises';
import { join } from 'path';
import { kstDateKey } from './time';

export const UPLOAD_DIR = join(process.cwd(), 'uploads');

/** Stores small JPEG snapshots on disk and returns their public URL. */
@Injectable()
export class SnapshotStore {
  async save(base64?: string | null, at: Date = new Date()): Promise<string | null> {
    if (!base64) return null;
    const data = Buffer.from(base64, 'base64');
    if (data.length < 4 || data[0] !== 0xff || data[1] !== 0xd8) return null;   // JPEG magic bytes only
    const day = kstDateKey(at);
    const name = `${randomUUID()}.jpg`;
    await mkdir(join(UPLOAD_DIR, day), { recursive: true });
    await writeFile(join(UPLOAD_DIR, day, name), data);
    return `/uploads/${day}/${name}`;
  }
}
