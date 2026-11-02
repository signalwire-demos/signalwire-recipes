/**
 * The recorder verify.py drives. Through a captured fetch it creates a room
 * from the plan verify.py hands it, lists, reads it and its addresses, raises
 * the member cap, deletes it, then tries a cap above the spec's maximum, and
 * prints what it captured as JSON.
 *
 * The expected values live in verify.py, which holds this output and the
 * Python surface's requests to the same one set.
 */
type Captured = { method: string; path: string; query: string; body: unknown };
const captured: Captured[] = [];
const [planJson = "{}", roomId = "room-1", newCap = "20"] = process.argv.slice(2);
const plan = JSON.parse(planJson) as { name: string } & Record<string, unknown>;

const room = {
  id: roomId, display_name: plan.name, type: "video_room",
  conference_room: { id: roomId, name: plan.name, enable_room_previews: true,
                     sync_audio_video: false, max_members: plan["max_members"] },
};
// the responses the platform would give, in request order; the delete is a
// 204 with no body
const responses: Array<[number, unknown]> = [
  [200, room],                                   // POST create
  [200, { data: [room] }],                       // GET list
  [200, room],                                   // GET one
  [200, { data: [{ id: "addr-1", name: plan.name, type: "room" }] }],
  [200, room],                                   // GET one, before the PUT
  [200, { ...room, conference_room: { ...room.conference_room, max_members: 20 } }],
  // a room whose sync flag comes back null, which the response schema allows
  [200, { ...room, conference_room: { ...room.conference_room, sync_audio_video: null } }],
  [200, room],                                   // the PUT's answer
  [204, null],                                   // DELETE
];

// HttpClient captures globalThis.fetch when the client is built, so it is
// replaced before index.ts is imported
globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const url = new URL(String(input));
  captured.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    query: url.search,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  const [status, body] = responses[captured.length - 1] ?? [200, {}];
  return new Response(body === null ? null : JSON.stringify(body), {
    status, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

const recipe = await import("./index.js");

await recipe.createRoom(plan as unknown as import("./index.js").RoomPlan);
await recipe.listRooms();
await recipe.getRoom(roomId);
await recipe.addressesOf(roomId);
await recipe.updateRoom(roomId, { max_members: Number(newCap) });
await recipe.updateRoom(roomId, { display_name: "Stand-up" });
const deleted = await recipe.deleteRoom(roomId);

const before = captured.length;
let refused = false;
try {
  await recipe.createRoom({ name: plan.name, max_members: recipe.MAX_MEMBERS + 1 });
} catch (error) {
  refused = String((error as Error).message).includes(String(recipe.MAX_MEMBERS));
}

console.log(JSON.stringify({ captured: captured.slice(0, before), deleted, refused,
                             afterRefusal: captured.length - before,
                             maxMembers: recipe.MAX_MEMBERS,
                             maxRemoveAfter: recipe.MAX_REMOVE_AFTER }));
