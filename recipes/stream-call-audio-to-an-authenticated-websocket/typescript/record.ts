/**
 * The recorder verify.py drives. It swaps the client's fetch, tries a ws:// url
 * and an unknown track, then opens the stream with and without its optional
 * keys and stops it, printing what it captured as JSON on stdout.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import { client, start, stop, type Track } from "./index.js";

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

const [callId = "", url = "", statusUrl = "", tag = ""] = process.argv.slice(2);

const refused: string[] = [];
for (const [badUrl, badTrack] of [["ws://media.example.com/calls", "both_tracks"],
                                  [url, "left_track"]]) {
  try {
    await start(callId, badUrl, badTrack as Track);
    refused.push("SENT");
  } catch (error) {
    refused.push(String((error as Error).message));
  }
}

await start(callId, url, "both_tracks", undefined, statusUrl, tag);
await start(callId, url);
await stop(callId);

console.log(JSON.stringify({ refused, captured }));
