import { WebSocketGateway, WebSocketServer } from '@nestjs/websockets';
import { Server } from 'socket.io';

/** Pushes new gate events to every open dashboard. */
@WebSocketGateway({ cors: { origin: '*' } })
export class EventsGateway {
  @WebSocketServer() server: Server;

  emit(event: 'vehicle' | 'attendance' | 'alert', payload: unknown) {
    this.server?.emit(event, payload);
  }
}
