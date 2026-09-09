/**
 * Forward an inbound SMS to other numbers.
 *
 * A text arriving on your number goes on to a list of recipients, prefixed
 * with the sender, and the sender gets no reply. `reply` is the Messaging SWML
 * method that sends a message; its `to` defaults to the sender, so naming `to`
 * is what turns a reply into a forward. The reference's own example is headed
 * "Forward an inbound message to another number".
 *
 * Written against @signalwire/sdk 2.0.5 and node:http.
 *
 *     npm start            # serves POST /inbound
 */
import "dotenv/config";
import { createServer, type IncomingMessage } from "node:http";

// who gets the copies, comma separated, E.164
export const RECIPIENTS = (process.env["FORWARD_TO"] ?? "+15550100001,+15550100002")
  .split(",").map((n) => n.trim()).filter(Boolean);
const AUTH_USER = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const AUTH_PASSWORD = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";

// the carrier keywords; see handle-opt-outs-yourself for what to do with them
const STOP_WORDS = new Set(["stop", "stopall", "unsubscribe", "cancel", "end", "quit"]);
// the platform's maximum SMS body, which the sender prefix eats into
const MAX_BODY = 1600;

const digits = (n: string | undefined) => (n ?? "").replace(/\D/g, "");

/** The bare word a phone sent, with the punctuation people add. */
const keyword = (body: string | undefined) =>
  (body ?? "").trim().replace(/^[.!? ]+|[.!? ]+$/g, "").toLowerCase();

/**
 * Everyone on the list once, except the sender and the receiving line.
 * Leaving the receiving line in would text the number that just fired this
 * webhook, which fires it again and forwards a second copy to everyone.
 */
export function targets(sender: string | undefined, receivedOn: string | undefined,
                        recipients = RECIPIENTS) {
  const skip = new Set([digits(sender), digits(receivedOn)]);
  const out: string[] = [];
  for (const r of recipients) {
    if (!skip.has(digits(r))) {
      skip.add(digits(r));               // a repeated entry is still one copy
      out.push(r);
    }
  }
  return out;
}

/** The sender, then their words, inside the platform's body limit. */
export function forwardedBody(sender: string, body: string | undefined) {
  const prefix = `${sender}: `;
  return prefix + (body ?? "").slice(0, MAX_BODY - prefix.length);
}

/** One reply per recipient, from the number that received the text. */
export function forwardDocument(sender: string, receivedOn: string,
                                body: string | undefined, recipients = RECIPIENTS) {
  const steps: Record<string, unknown>[] = [];
  if (!STOP_WORDS.has(keyword(body))) {
    for (const recipient of targets(sender, receivedOn, recipients)) {
      // `to` is what makes this a forward rather than a reply
      steps.push({ reply: { to: recipient, from: receivedOn,
                            body: forwardedBody(sender, body) } });
    }
  }
  // an opt-out is for you, not for the team; an empty document sends nothing
  return { version: "1.0.0", sections: { main: steps } };
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("error", reject);
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
  });
}

/** POST /inbound, behind the basic auth in the URL you give SignalWire. */
export function serve(port: number) {
  const pair = Buffer.from(`${AUTH_USER}:${AUTH_PASSWORD}`).toString("base64");
  const expected = `Basic ${pair}`;
  return createServer(async (req, res) => {
    const send = (status: number, body: unknown,
                  headers: Record<string, string> = {}) => {
      res.writeHead(status, { "content-type": "application/json", ...headers });
      res.end(JSON.stringify(body));
    };
    // the credentials decide before the body is read
    if (!AUTH_USER || req.headers.authorization !== expected) {
      return send(401, {}, { "www-authenticate": 'Basic realm="forward"' });
    }
    if (req.method !== "POST" || req.url !== "/inbound") return send(404, {});
    const raw = await readBody(req);
    let payload: { message?: Record<string, string> } = {};
    try { payload = JSON.parse(raw); } catch { return send(400, { error: "bad json" }); }
    const m = payload.message ?? {};
    // the webhook's schema requires both; without them there is nothing to do
    if (!m["from"] || !m["to"]) {
      return send(400, { error: "message.from and message.to are required" });
    }
    send(200, forwardDocument(m["from"], m["to"], m["body"]));
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const name of ["SWML_BASIC_AUTH_USER", "SWML_BASIC_AUTH_PASSWORD"]) {
    if (!process.env[name]) throw new Error(`${name} is required; see .env.example`);
  }
  serve(Number(process.env["PORT"] ?? 8080));
  console.log("listening: POST /inbound");
}
