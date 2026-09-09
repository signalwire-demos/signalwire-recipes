/**
 * The recorder verify.py drives. It swaps the client's fetch, calls the four
 * helpers plus a start with no status URL, and prints every captured request as
 * JSON on stdout.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import { client, start, pause, resume, stop } from "./index.js";

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

const callId = process.argv[2] ?? "";
const statusUrl = process.argv[3] ?? "";

await start(callId, statusUrl);
await pause(callId);
await resume(callId);
await stop(callId);
await start(callId);

console.log(JSON.stringify({ captured }));
