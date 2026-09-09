/**
 * The recorder verify.py drives. It swaps the client's fetch, tries a tel: and
 * a sips: URI, then refers with and without the optional keys, printing what it
 * captured as JSON on stdout.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import { client, refer } from "./index.js";

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

const [callId = "", to = "", fromUri = "", statusUrl = ""] = process.argv.slice(2);

const refused: string[] = [];
for (const [badTo, badFrom] of [["tel:+14155550123", ""],
                                [to, "sips:queue@pbx.example.com"]]) {
  try {
    await refer(callId, badTo, badFrom || undefined);
    refused.push("SENT");
  } catch (error) {
    refused.push(String((error as Error).message));
  }
}

await refer(callId, to, fromUri, statusUrl);
await refer(callId, to);

console.log(JSON.stringify({ refused, captured }));
