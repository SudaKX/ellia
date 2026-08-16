import type { WebSocket } from 'ws'

export interface RoomMember {
  connectionId: string
  userId: string
  username: string
  ws: WebSocket
}

type Room = Map<string, RoomMember>

const rooms = new Map<string, Room>()

function roomOf(projectId: string): Room {
  let room = rooms.get(projectId)
  if (!room) {
    room = new Map()
    rooms.set(projectId, room)
  }
  return room
}

export function joinRoom(projectId: string, member: RoomMember): void {
  roomOf(projectId).set(member.connectionId, member)
}

export function leaveRoom(projectId: string, connectionId: string): void {
  const room = rooms.get(projectId)
  if (!room) return
  room.delete(connectionId)
  if (room.size === 0) rooms.delete(projectId)
}

export function listRoom(projectId: string): RoomMember[] {
  return [...roomOf(projectId).values()]
}

export function broadcastRoom(
  projectId: string,
  message: unknown,
  exceptConnectionId?: string,
): void {
  const payload = JSON.stringify(message)
  for (const member of roomOf(projectId).values()) {
    if (member.connectionId === exceptConnectionId) continue
    if (member.ws.readyState === member.ws.OPEN) {
      member.ws.send(payload)
    }
  }
}
