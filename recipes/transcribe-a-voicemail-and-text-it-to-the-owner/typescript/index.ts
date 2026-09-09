/**
 * Transcribe a voicemail and text it to the owner.
 *
 * `<Record transcribe="true" transcribeCallback="...">` makes the platform
 * transcribe the recording and POST the words to your URL. That payload
 * carries the transcription and the recording, but not the caller, so the
 * caller's number rides in the callback URL the document is built with. The
 * handler texts the owner the words and the link.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.compat) and node:http.
 *
 *     npm start            # serves POST /voice and POST /transcription
 */
import "dotenv/config";
import { createHmac, timingSafeEqual } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import { join } from "node:path";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// where this app is reachable; the callback URL is built from it
export const PUBLIC_URL = (process.env["PUBLIC_URL"]
  ?? "https://your-host.example.com").replace(/\/+$/, "");
// the person who gets the voicemail, and the messaging number it comes from
const OWNER = process.env["OWNER_NUMBER"] ?? "+15550100001";
const SMS_FROM = process.env["SMS_FROM"] ?? "+15550001111";
// the project's signing key, from the Dashboard
const SIGNING_KEY = process.env["SIGNALWIRE_SIGNING_KEY"] ?? "";
// one marker file per transcription already texted; swap for a unique key in
// your table
const SEEN_DIR = process.env["SEEN_DIR"] ?? "voicemails-seen";

export const GREETING = "No one is free right now. Leave a message after the beep.";
export const MAX_SECONDS = 120;

const DIGESTS: Record<string, string> = {
  "x-signalwire-sha256-signature": "sha256", "x-signalwire-signature": "sha1",
};

/** True only when a signature header is present and matches; SHA-256 wins. */
export function signed(headers: Record<string, string | undefined>, url: string,
                       rawBody: Buffer, key = SIGNING_KEY): boolean {
  for (const [header, algorithm] of Object.entries(DIGESTS)) {
    const sent = headers[header];
    if (sent !== undefined) {
      if (!/^[0-9a-fA-F]+$/.test(sent)) return false;
      const want = createHmac(algorithm, key)
        .update(Buffer.concat([Buffer.from(url), rawBody])).digest("hex");
      return sent.length === want.length
        && timingSafeEqual(Buffer.from(sent), Buffer.from(want));
    }
  }
  return false;
}

/**
 * Reserve this transcription, atomically. False when already taken. Check then
 * act would let two concurrent callbacks both text the owner; "wx" is O_EXCL.
 */
export function claim(transcriptionSid: string) {
  mkdirSync(SEEN_DIR, { recursive: true });
  const safe = (transcriptionSid || "none").replace(/[^A-Za-z0-9_-]/g, "_");
  try {
    writeFileSync(join(SEEN_DIR, safe), "", { flag: "wx" });
    return true;
  } catch (error) {
    // only an existing marker means already texted
    if ((error as { code?: string }).code === "EEXIST") return false;
    throw error;
  }
}

/** The transcription payload has no caller, so it travels in the URL. */
export const callbackUrl = (caller: string | undefined) =>
  `${PUBLIC_URL}/transcription?from=${encodeURIComponent(caller || "unknown")}`;

const escapeXml = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

/** cXML: greet, then record with transcription turned on. */
export const voicemailDocument = (caller: string | undefined) =>
  '<?xml version="1.0" encoding="UTF-8"?>\n'
  + "<Response>\n"
  + `  <Say>${escapeXml(GREETING)}</Say>\n`
  + '  <Record transcribe="true" '
  + `transcribeCallback="${escapeXml(callbackUrl(caller))}" `
  + `maxLength="${MAX_SECONDS}" playBeep="true" finishOnKey="#" timeout="5"/>\n`
  + "</Response>\n";

type Payload = Record<string, string>;

/** One text to the owner. `completed` carries the words; `failed` does not. */
export function notify(caller: string, payload: Payload) {
  const body = payload["TranscriptionStatus"] === "completed"
    ? `Voicemail from ${caller}: ${payload["TranscriptionText"] ?? ""}\n`
      + `${payload["RecordingUrl"] ?? ""}`
    : `Voicemail from ${caller}, not transcribed.\n${payload["RecordingUrl"] ?? ""}`;
  return client.compat.messages.create({ To: OWNER, From: SMS_FROM, Body: body });
}

/**
 * Text the owner once per transcription. The claim comes before the send and
 * is not released on failure: a request that reached SignalWire and lost its
 * response looks like one that never arrived, so at most one text per
 * transcription is the safer failure.
 */
export async function handle(caller: string, payload: Payload) {
  if (!claim(payload["TranscriptionSid"] ?? "")) {
    return { texted: false, reason: "already texted" };
  }
  const message = (await notify(caller, payload)) as { sid?: string };
  return { texted: true, sid: message.sid };
}

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
  });
}

/** A form-encoded or JSON body, as the platform may send either. */
function parse(raw: Buffer, contentType: string | undefined): Payload {
  const text = raw.toString();
  if ((contentType ?? "").includes("json")) {
    try { return JSON.parse(text) as Payload; } catch { return {}; }
  }
  return Object.fromEntries(new URLSearchParams(text));
}

export function serve(port: number) {
  return createServer(async (req, res) => {
    const send = (status: number, body: unknown, type = "application/json") => {
      res.writeHead(status, { "content-type": type });
      res.end(typeof body === "string" ? body : JSON.stringify(body));
    };
    try {
      const raw = await readBody(req);
      const target = new URL(req.url ?? "/", "http://local");
      if (req.method !== "POST") return send(404, {});
      const payload = parse(raw, req.headers["content-type"]);
      if (target.pathname === "/voice") {
        return send(200, voicemailDocument(payload["From"]), "text/xml");
      }
      if (target.pathname === "/transcription") {
        // the signature covers the URL SignalWire posted to, query included
        const url = PUBLIC_URL + target.pathname + target.search;
        const headers = Object.fromEntries(Object.entries(req.headers)
          .map(([k, v]) => [k, Array.isArray(v) ? v[0] : v]));
        if (!signed(headers, url, raw)) return send(403, {});
        const caller = target.searchParams.get("from") ?? "unknown";
        return send(200, await handle(caller, payload));
      }
      send(404, {});
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
  console.log("listening: POST /voice, POST /transcription");
}
