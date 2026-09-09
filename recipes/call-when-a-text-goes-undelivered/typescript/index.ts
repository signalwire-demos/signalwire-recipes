/**
 * Call when a text goes undelivered.
 *
 * A message status callback that reports `undelivered` or `failed` carries the
 * recipient and the body, so one `POST /api/calling/calls` with inline SWML
 * places a call that speaks the same message. The callback is checked against
 * SignalWire's signature before it spends anything, and each message id is
 * claimed with an atomic marker before the call is placed, so two deliveries
 * of one callback cannot place two calls.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling) and node:http.
 *
 *     npm start            # serves POST /message-status
 */
import "dotenv/config";
import { createHmac, timingSafeEqual } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import { join } from "node:path";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// a voice-capable number you own; the call comes from it
export const FROM = process.env["VOICE_FROM"] ?? "+15550001111";
// the status_callback URL you gave when sending. The signature is over the URL
// SignalWire posted to, so the configured query is stripped here and the
// request's own is appended below; otherwise a tagged URL would be signed twice.
export const STATUS_URL = process.env["STATUS_URL"]
  ?? "https://your-host.example.com/message-status";
const PARTS = new URL(STATUS_URL);
export const STATUS_PATH = PARTS.pathname;
const STATUS_BASE = PARTS.origin + PARTS.pathname;
// the project's signing key, from the Dashboard
const SIGNING_KEY = process.env["SIGNALWIRE_SIGNING_KEY"] ?? "";
// one marker file per message id already called; swap for a unique key in your table
const HANDLED_DIR = process.env["HANDLED_DIR"] ?? "handled-messages";

// the two statuses that mean the text will not arrive
const FALLBACK_ON = new Set(["undelivered", "failed"]);

const DIGESTS: Record<string, string> = {
  "x-signalwire-sha256-signature": "sha256", "x-signalwire-signature": "sha1",
};

/** The URL the signature is over: the configured one, with this query. */
export const signedUrl = (queryString = "") =>
  STATUS_BASE + (queryString ? `?${queryString}` : "");

/** True only when a signature header is present and matches; SHA-256 wins. */
export function signed(headers: Record<string, string | undefined>, url: string,
                       rawBody: Buffer, key = SIGNING_KEY): boolean {
  if (!key) return false;              // an empty key would verify anything
  for (const [header, algorithm] of Object.entries(DIGESTS)) {
    const sent = headers[header];
    if (sent !== undefined) {
      if (!/^[0-9a-fA-F]+$/.test(sent)) return false;
      const want = createHmac(algorithm, key)
        .update(Buffer.concat([Buffer.from(url), rawBody])).digest("hex");
      const lower = sent.toLowerCase();
      return lower.length === want.length
        && timingSafeEqual(Buffer.from(lower), Buffer.from(want));
    }
  }
  return false;
}

const marker = (messageId: string) =>
  join(HANDLED_DIR, messageId.replace(/[^A-Za-z0-9_-]/g, "_"));

/** Reserve this message id, atomically. False when it was already taken. */
export function claim(messageId: string) {
  mkdirSync(HANDLED_DIR, { recursive: true });
  try {
    // "wx" is O_EXCL: two callers cannot both win this
    writeFileSync(marker(messageId), "", { flag: "wx" });
    return true;
  } catch (error) {
    // Only an existing marker means already handled. A read-only directory or
    // a full disk must not be reported as a call that was already placed, or
    // the webhook is acknowledged and the fallback never happens.
    if ((error as { code?: string }).code === "EEXIST") return false;
    throw error;
  }
}

/** One line. A newline in the body would fail the play url's own pattern. */
export const spoken = (body: string) =>
  "We could not reach you by text. The message was: "
  + body.split(/\s+/).filter(Boolean).join(" ");

/** Answer, speak the text, hang up: the whole call, inline in the request. */
export const callDocument = (body: string) => ({
  version: "1.0.0",
  sections: { main: [{ answer: {} }, { play: { url: `say:${spoken(body)}` } },
                     { hangup: {} }] },
});

/** One request. */
export function placeCall(to: string, body: string) {
  return client.calling.dial({ from: FROM, to, swml: callDocument(body), timeout: 25 });
}

type Event = { id?: string; status?: string; to?: string; body?: string };

/** Fall back only for a final failure, and only once per message. */
export async function handle(event: Event) {
  const { status, id, to } = event;
  if (!status || !FALLBACK_ON.has(status)) {
    return { called: false, reason: String(status ?? "none") };
  }
  // the spec requires both; without them there is nothing to call or to key on
  if (!id) return { called: false, reason: "no message id" };
  if (!to) return { called: false, reason: "no recipient" };
  if (!claim(id)) return { called: false, reason: "already handled" };
  // The claim stays whatever happens next. A request that reached SignalWire
  // and lost its response looks exactly like one that never arrived, so
  // releasing here would let a redelivery place a second billed call. At most
  // one call per message is the safer failure, and the marker is where a
  // reconciler looks; see Limitations.
  const call = (await placeCall(to, event.body ?? "")) as { id?: string };
  return { called: true, call_id: String(call.id ?? "") };
}

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("error", reject);
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
  });
}

/** POST to the configured path, refused unless SignalWire signed it. */
export function serve(port: number) {
  return createServer(async (req, res) => {
    try {
      const raw = await readBody(req);
      const target = new URL(req.url ?? "/", "http://local");
      // the raw query, not a re-serialised one: SignalWire signs the literal
      // URL it requested, and searchParams.toString() normalises %20 to +
      const url = signedUrl(target.search.replace(/^\?/, ""));
      const headers = Object.fromEntries(Object.entries(req.headers)
        .map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]));
      if (req.method !== "POST" || target.pathname !== STATUS_PATH
          || !signed(headers, url, raw)) {
        res.writeHead(403);
        return res.end();
      }
      let event: Event = {};
      try { event = JSON.parse(raw.toString()); } catch { /* no body, no status */ }
      const answer = await handle(event);
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify(answer));
  } catch (error) {
    // node:http does not await this listener, so a rejection escaping it is
    // unhandled and ends the process. A storage fault or a failed request is
    // a 500 the platform can retry; the claim stays, so a retry that finds it
    // does nothing and at most one action is taken.
    console.error(error);
    if (!res.headersSent) res.writeHead(500, { "content-type": "application/json" });
    res.end(JSON.stringify({ error: "internal" }));
  }
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  if (!SIGNING_KEY) {
    throw new Error("SIGNALWIRE_SIGNING_KEY is required; see .env.example");
  }
  serve(Number(process.env["PORT"] ?? 8080));
  console.log(`listening: POST ${STATUS_PATH}`);
}
