/**
 * The recorder verify.py drives. It swaps the client's fetch, refuses four bad
 * names, creates two addresses, and prints what it captured as JSON.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import { client, giveAddress, dialString } from "./index.js";

type Captured = { method: string; path: string; body: unknown };
const captured: Captured[] = [];
const [agentId = "", name = "", uri = ""] = process.argv.slice(2);

const recorder: typeof fetch = async (input, init) => {
  const url = new URL(String(input));
  captured.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  const user = captured.length === 1 ? "*" : "reception";
  return new Response(JSON.stringify({
    id: `addr-${captured.length}`, type: "sip_address", resource_id: agentId, name,
    user, uri: uri.replace("*", user), context: "public", encryption: "required",
  }), { status: 200, headers: { "content-type": "application/json" } });
};

// the seam the Python verifier uses, where it swaps client._http
(client.calling as unknown as { _http: { _fetch: typeof fetch } })._http._fetch = recorder;

let refused = 0;
for (const bad of ["Front Desk", "front_desk", "Front-Desk", ""]) {
  try {
    await giveAddress(agentId, bad);
  } catch (error) {
    if (String((error as Error).message).includes("lowercase")) refused += 1;
  }
}

const first = await giveAddress(agentId, name);
await giveAddress(agentId, name, "reception");

console.log(JSON.stringify({ refused, captured, dial: dialString(first) }));
