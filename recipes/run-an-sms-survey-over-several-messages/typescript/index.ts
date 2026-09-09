/**
 * Run an SMS survey over several messages.
 *
 * A survey is one outbound text and then a conversation the platform does not
 * hold for you. Each reply arrives at your inbound webhook on its own, so the
 * state that says which question a number is on lives in a file here, keyed by
 * the sender. The webhook answers with a messaging SWML `reply` carrying the
 * next question, a re-ask for an answer that does not parse, or the closing
 * line.
 *
 * STOP ends everything for that number, and a number that has stopped is never
 * sent a first question. Only SignalWire may post to the webhook: the signature
 * is checked before any state changes.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient) and the documented inbound
 * message webhook and messaging SWML.
 *
 *     npm start                          # serve /inbound and /begin
 *     npm start begin +14155550123       # text the first question
 */
import "dotenv/config";
import { createHmac, timingSafeEqual } from "node:crypto";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import { RestClient } from "@signalwire/sdk";

export const client = new RestClient();
// 2.0.5 has no messaging namespace; the send goes through the shared HttpClient
const http = (client.calling as unknown as {
  _http: { post(path: string, body: unknown): Promise<unknown> };
})._http;

export const FROM = process.env["SMS_FROM"] ?? "";
export const SIGNING_KEY = process.env["SIGNALWIRE_SIGNING_KEY"] ?? "";
export const INBOUND_URL = process.env["INBOUND_URL"] ?? "";
// /begin sends billable texts with your credentials, so it is behind a key the
// server holds and your own systems present as X-Survey-Key
export const ADMIN_KEY = process.env["SURVEY_ADMIN_KEY"] ?? "";

// where each number's progress lives; swap for your database
export const STATE_PATH = process.env["SURVEY_STATE_PATH"] ?? "survey-state.json";

// the platform signs its webhooks: hex(HMAC(signing_key, url + raw_body)), SHA-256
// on call requests, SHA-1 on every signed request (docs/swml/guides/webhook-security)
const DIGESTS: Record<string, string> = {
  "x-signalwire-sha256-signature": "sha256", "x-signalwire-signature": "sha1",
};

type Kind = "scale" | "yes_no" | "text";
// the questions, in order: a key for the answer, the text, and how to read a reply
export const QUESTIONS: [string, string, Kind][] = [
  ["rating", "Thanks for visiting Ridgeline Cycles. How was your service today? "
             + "Reply with a number from 1 to 5.", "scale"],
  ["recommend", "Would you recommend us to a friend? Reply YES or NO.", "yes_no"],
  ["comment", "Anything we should know? Reply with a sentence, or SKIP.", "text"],
];
export const DONE = "That is everything. Thank you. Reply STOP at any time to opt out.";
const REASK: Partial<Record<Kind, string>> = {
  scale: "Please reply with a single number from 1 to 5.",
  yes_no: "Please reply YES or NO.",
};

// the single words that end the survey, compared whole after trim and lowercase
const STOP_WORDS = new Set(["stop", "stopall", "unsubscribe", "cancel", "end", "quit"]);
export const STOPPED = "You will receive no more messages from Ridgeline Cycles.";

export type Record_ = {
  step: number; answers: Record<string, unknown>; stopped: boolean;
  seen?: Record<string, string>;
};
type State = Record<string, Record_>;
export type Message = {
  message_id: string; from: string; to: string; body: string | null;
};
type Swml = { version: string; sections: { main: unknown[] } };

export class OptedOut extends Error {}

function load(): State {
  return existsSync(STATE_PATH) ? JSON.parse(readFileSync(STATE_PATH, "utf-8")) : {};
}

function save(state: State) {
  writeFileSync(`${STATE_PATH}.tmp`, JSON.stringify(state, null, 2), "utf-8");
  renameSync(`${STATE_PATH}.tmp`, STATE_PATH);
}

const keyword = (body: string | null | undefined) => (body ?? "").trim().toLowerCase();

/** The answer a reply means, or null when it does not fit the question. */
export function parse(kind: Kind, body: string | null): unknown {
  const word = keyword(body);
  if (kind === "scale") {
    return ["1", "2", "3", "4", "5"].includes(word) ? Number(word) : null;
  }
  if (kind === "yes_no") {
    const answers: Record<string, boolean> = { yes: true, y: true, no: false, n: false };
    return answers[word] ?? null;
  }
  return word === "skip" ? "" : (body ?? "").trim() || null;
}

/** A messaging SWML document with one verb: the text back to the sender. */
export const reply = (text: string): Swml =>
  ({ version: "1.0.0", sections: { main: [{ reply: { body: text } }] } });

export const silence = (): Swml => ({ version: "1.0.0", sections: { main: [] } });

/** Text the first question. A number that said STOP is refused, not texted. */
export async function begin(to: string) {
  const state = load();
  if (state[to]?.stopped) throw new OptedOut(`${to} opted out; no message sent`);
  state[to] = { step: 0, answers: {}, stopped: false };
  save(state);
  return http.post("/api/messaging/messages", { to, from: FROM, body: QUESTIONS[0][1] });
}

/** Advance one number's survey by one reply. Returns the SWML to run. */
export function handleInbound(message: Message): Swml {
  const sender = message.from;
  const state = load();
  const record = state[sender];
  const word = keyword(message.body);

  if (STOP_WORDS.has(word)) {
    state[sender] = { ...(record ?? { step: 0, answers: {} }), stopped: true };
    save(state);
    return reply(STOPPED);
  }
  if (!record || record.stopped) {
    // not in a survey, or out of it: nothing is sent and nothing is recorded.
    // This runs before the cache, or a late retry of an earlier answer would
    // text a question to a number that said STOP
    return silence();
  }
  const seen = record.seen ?? {};
  if (message.message_id in seen) {
    // the webhook was delivered again, maybe late: the answer it got the first
    // time, and the state is not touched. A retried rating parsed at the
    // comment step would otherwise be stored as the comment
    return reply(seen[message.message_id]);
  }
  if (record.step >= QUESTIONS.length) return silence();

  const [key, question, kind] = QUESTIONS[record.step];
  const answer = parse(kind, message.body);
  if (answer === null) return reply(REASK[kind] ?? question);

  record.answers[key] = answer;
  record.step += 1;
  const text = record.step === QUESTIONS.length ? DONE : QUESTIONS[record.step][1];
  (record.seen ??= {})[message.message_id] = text;
  save(state);
  return reply(text);
}

/** True only when a signature header is present and matches. */
export function signed(headers: Record<string, string | undefined>, url: string,
                       rawBody: Buffer, key = SIGNING_KEY): boolean {
  for (const [header, algorithm] of Object.entries(DIGESTS)) {
    const sent = headers[header];
    if (sent) {
      const expected = createHmac(algorithm, key)
        .update(Buffer.concat([Buffer.from(url), rawBody])).digest("hex");
      return sent.length === expected.length
        && timingSafeEqual(Buffer.from(sent), Buffer.from(expected));
    }
  }
  return false;
}

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks)));
  });
}

/** The two routes: SignalWire posts to /inbound, you post to /begin. */
export function serve(port: number) {
  return createServer(async (req, res) => {
    const raw = await readBody(req);
    const send = (status: number, body: unknown) => {
      res.writeHead(status, { "content-type": "application/json" });
      res.end(JSON.stringify(body));
    };
    if (req.method === "POST" && req.url?.startsWith("/inbound")) {
      const query = req.url.includes("?") ? req.url.slice(req.url.indexOf("?")) : "";
      if (!signed(req.headers as Record<string, string>, INBOUND_URL + query, raw)) {
        return send(403, { error: "unsigned" });
      }
      return send(200, handleInbound(JSON.parse(raw.toString()).message));
    }
    if (req.method === "POST" && req.url === "/begin") {
      // your systems start a survey here, never the public internet
      if (!ADMIN_KEY || req.headers["x-survey-key"] !== ADMIN_KEY) {
        return send(403, { error: "no survey key" });
      }
      try {
        return send(200, await begin(JSON.parse(raw.toString()).to));
      } catch (error) {
        if (error instanceof OptedOut) return send(409, { error: error.message });
        throw error;
      }
    }
    send(404, { error: "no such route" });
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const [name, value] of Object.entries({ SMS_FROM: FROM, SIGNALWIRE_SIGNING_KEY:
      SIGNING_KEY, INBOUND_URL, SURVEY_ADMIN_KEY: ADMIN_KEY })) {
    if (!value) throw new Error(`${name} is required; see .env.example`);
  }
  if (process.argv[2] === "begin" && process.argv[3]) {
    console.log(await begin(process.argv[3]));
  } else {
    serve(Number(process.env["PORT"] ?? 8080));
    console.log("listening: POST /inbound (signed), POST /begin {\"to\": ...}");
  }
}
