/**
 * The recorder verify.py drives. It swaps the client's fetch, refuses a
 * fractional hold, calls the three helpers, and prints what it captured as JSON
 * on stdout.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import { client, hold, unhold, stop } from "./index.js";

type Captured = { method: string; path: string; body: unknown };
const captured: Captured[] = [];

const recorder: typeof fetch = async (input, init) => {
  const url = new URL(String(input));
  captured.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
};

// the seam the Python verifier uses, where it swaps client._http
(client.calling as unknown as { _http: { _fetch: typeof fetch } })._http._fetch = recorder;

const [callId = "", seconds = "90"] = process.argv.slice(2);

const refused: string[] = [];
try {
  await hold(callId, 1.5);
  refused.push("SENT");
} catch (error) {
  refused.push(String((error as Error).message));
}

await hold(callId, Number(seconds));
await unhold(callId);
await stop(callId);

console.log(JSON.stringify({ refused, captured }));
