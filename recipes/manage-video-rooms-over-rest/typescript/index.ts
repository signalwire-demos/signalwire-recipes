/**
 * Manage video rooms over REST.
 *
 * A video room is a Fabric Conference Room resource, and one REST family
 * creates, lists, reads, updates and deletes it:
 * /api/fabric/resources/conference_rooms. A room per meeting is a create with
 * a member cap and a join window. A meeting that is over is a delete. The SDK
 * wraps the calls as client.fabric.conferenceRooms.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.fabric).
 *
 *     npm start create standup-0900 12 2026-11-03T08:50:00Z 2026-11-03T09:30:00Z
 *     npm start list
 *     npm start show <room_id>
 *     npm start update <room_id> 20
 *     npm start delete <room_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// The spec's bounds: max_members is 0 to 300, remove_after_seconds_elapsed is
// 0 to 200000. Outside them the platform answers 422, so the helpers refuse
// the value before any request is made.
export const MAX_MEMBERS = 300;
export const MAX_REMOVE_AFTER = 200_000;

export interface RoomPlan {
  name: string;
  display_name?: string;
  enable_room_previews?: boolean;
  max_members?: number;
  join_from?: string;
  join_until?: string;
  remove_at?: string;
  remove_after_seconds_elapsed?: number;
  [option: string]: unknown;
}

type Room = Record<string, unknown>;

function bounded(key: string, value: number, top: number): number {
  if (!Number.isInteger(value) || value < 0 || value > top) {
    throw new Error(`${key} must be between 0 and ${top}, not ${value}`);
  }
  return value;
}

/**
 * A room per meeting. `max_members` caps the room, `join_from` and
 * `join_until` bound when joining works, `remove_at` empties the room at a
 * time, and `remove_after_seconds_elapsed` removes each participant that long
 * after they joined. Times are ISO 8601 with a zone. `enable_room_previews`
 * is the one other field the create requires.
 */
export async function createRoom(plan: RoomPlan): Promise<Room> {
  const { max_members, remove_after_seconds_elapsed, ...rest } = plan;
  const body: Room = {
    ...rest,
    display_name: plan.display_name ?? plan.name,
    enable_room_previews: plan.enable_room_previews ?? false,
  };
  if (max_members !== undefined) {
    body["max_members"] = bounded("max_members", max_members, MAX_MEMBERS);
  }
  if (remove_after_seconds_elapsed !== undefined) {
    body["remove_after_seconds_elapsed"] = bounded(
      "remove_after_seconds_elapsed", remove_after_seconds_elapsed, MAX_REMOVE_AFTER);
  }
  return client.fabric.conferenceRooms.create(body);
}

/** Every conference room in the project. */
export async function listRooms(): Promise<Room> {
  return client.fabric.conferenceRooms.list();
}

export async function getRoom(roomId: string): Promise<Room> {
  return client.fabric.conferenceRooms.get(roomId);
}

/** The addresses a room answers at; the browser dials one of these. */
export async function addressesOf(roomId: string): Promise<Room> {
  return client.fabric.conferenceRooms.listAddresses(roomId);
}

/**
 * The update is a PUT, and the spec requires `enable_room_previews` and
 * `sync_audio_video` on every PUT. An update that changes neither has to
 * carry them anyway, so read the room first and send its current values. The
 * response schema lets sync_audio_video come back null; the request schema
 * does not take null, so an unset flag is sent as false.
 */
export async function updateRoom(roomId: string, changes: Room): Promise<Room> {
  const current = (await getRoom(roomId))["conference_room"] as Room;
  const body: Room = {
    enable_room_previews: current["enable_room_previews"] === true,
    sync_audio_video: current["sync_audio_video"] === true,
    ...changes,
  };
  if (typeof changes["max_members"] === "number") {
    body["max_members"] = bounded("max_members", changes["max_members"], MAX_MEMBERS);
  }
  return client.fabric.conferenceRooms.update(roomId, body);
}

/** A DELETE by id. The platform answers 204 with no body. */
export async function deleteRoom(roomId: string): Promise<{ deleted: string }> {
  await client.fabric.conferenceRooms.delete(roomId);
  return { deleted: roomId };
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, a, b, c, d] = process.argv.slice(2);
  let out: unknown;
  if (cmd === "create" && a) {
    out = await createRoom({ name: a, max_members: b ? Number(b) : undefined,
                             join_from: c, join_until: d });
  } else if (cmd === "list") {
    out = await listRooms();
  } else if (cmd === "show" && a) {
    out = { room: await getRoom(a), addresses: await addressesOf(a) };
  } else if (cmd === "update" && a && b) {
    out = await updateRoom(a, { max_members: Number(b) });
  } else if (cmd === "delete" && a) {
    out = await deleteRoom(a);
  } else {
    console.error("usage: see the comment at the top of index.ts");
    process.exit(2);
  }
  console.log(JSON.stringify(out, null, 2));
}
