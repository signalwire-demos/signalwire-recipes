/**
 * The recorder verify.py drives. It swaps the client's fetch, calls the three
 * helpers, and prints every captured request as JSON on stdout.
 *
 * This is the Node half of the recipe's proof. The expected values live in
 * verify.py, which compares this output and the Python surface's requests
 * against that one set.
 */
import { client, hangUp, transfer, unbridge, END_REASONS, type EndReason } from "./index.js";

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

// the same seam the Python verifier uses, where it swaps client._http
(client.calling as unknown as { _http: { _fetch: typeof fetch } })._http._fetch = recorder;

const refused: string[] = [];
try {
  await hangUp(process.argv[2] ?? "", "rejected" as EndReason);
} catch (error) {
  refused.push(String((error as Error).message));
}

const callId = process.argv[2] ?? "";
await hangUp(callId, "busy");
await transfer(callId, process.argv[3] ?? "");
await unbridge(callId);

const every: Captured[] = [];
const everyRecorder: typeof fetch = async (input, init) => {
  const url = new URL(String(input));
  every.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
};
(client.calling as unknown as { _http: { _fetch: typeof fetch } })._http._fetch = everyRecorder;
for (const reason of END_REASONS) await hangUp(callId, reason);
await hangUp(callId);

// the other documented form of dest: an inline SWML document rather than a URL
const inline: Captured[] = [];
const inlineRecorder: typeof fetch = async (input, init) => {
  const url = new URL(String(input));
  inline.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
};
(client.calling as unknown as { _http: { _fetch: typeof fetch } })._http._fetch =
  inlineRecorder;
await transfer(callId, { version: "1.0.0", sections: { main: [{ hangup: {} }] } });

console.log(JSON.stringify({
  reasons: [...END_REASONS], refused, captured, every, inline,
}));
