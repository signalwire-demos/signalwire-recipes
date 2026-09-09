/**
 * The recorder verify.py drives. It swaps the client's fetch, calls every
 * helper, and prints what it captured plus the refusals as JSON on stdout.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import {
  client, say, playFile, setVolume, stopPlayback, askDigits, askSpeech, stopCollect,
} from "./index.js";

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

const [callId = "", text = "", url = "", statusUrl = ""] = process.argv.slice(2);

// a collect with no status_url never reaches the wire, missing or empty
const refused: string[] = [];
for (const bad of [undefined, ""]) {
  for (const helper of [askDigits, askSpeech]) {
    try {
      await helper(callId, bad);
      refused.push("SENT");
    } catch (error) {
      refused.push(String((error as Error).message));
    }
  }
}
for (const bad of [41, Number("loud")]) {
  try {
    await setVolume(callId, bad);
    refused.push("SENT");
  } catch (error) {
    refused.push(String((error as Error).message));
  }
}
const beforeAnyRequest = captured.length;

await say(callId, text);
await say(callId, text, undefined, statusUrl);
await playFile(callId, url);
await setVolume(callId, Number("-6"));
await stopPlayback(callId);
await askDigits(callId, statusUrl);
await askSpeech(callId, statusUrl);
await stopCollect(callId);

console.log(JSON.stringify({ refused, beforeAnyRequest, captured }));
