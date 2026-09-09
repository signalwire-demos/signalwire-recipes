/**
 * Relay calls and texts through a proxy number.
 *
 * Two people share one number of yours and never learn each other's. Your
 * handler pairs them: a session says that on proxy P, participant A talks to B
 * and B talks to A. A call from A to P becomes `connect` to B with `from` set
 * to P, so B's phone shows the proxy; a text from A to P becomes a `reply` to
 * B from P.
 *
 * Written against @signalwire/sdk 2.0.5 (SWMLService) and node:http.
 *
 *     npm start            # serves POST /call, POST /message, POST /pair
 */
import "dotenv/config";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import { SWMLService } from "@signalwire/sdk";

// the number both parties see. Buy it first; buy-a-number-and-point-it-at-your-app
export const PROXY = process.env["PROXY_NUMBER"] ?? "+15550001111";
// where the pairings live; swap for your database
export const SESSIONS_PATH = process.env["SESSIONS_PATH"] ?? "proxy-sessions.json";
// /pair decides who can reach whom; it wants a key the server holds
const ADMIN_KEY = process.env["PROXY_ADMIN_KEY"] ?? "";
const AUTH_USER = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const AUTH_PASSWORD = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
export const NOT_ACTIVE = "This number is not active for your call.";

const digits = (n: string | undefined) => (n ?? "").replace(/\D/g, "");
const key = (proxy: string, participant: string) =>
  `${digits(proxy)}|${digits(participant)}`;

type Sessions = Record<string, string>;
const load = (): Sessions =>
  existsSync(SESSIONS_PATH) ? JSON.parse(readFileSync(SESSIONS_PATH, "utf-8")) : {};
function save(sessions: Sessions) {
  writeFileSync(`${SESSIONS_PATH}.tmp`, JSON.stringify(sessions, null, 2), "utf-8");
  renameSync(`${SESSIONS_PATH}.tmp`, SESSIONS_PATH);
}

/** On this proxy, A reaches B and B reaches A. Returns the two keys written. */
export function pair(a: string, b: string, proxy = PROXY): string[] {
  const sessions = load();
  // a participant is in one pairing at a time: drop the old partner's
  // route back, or the old partner could still reach them
  for (const participant of [a, b]) {
    const old = sessions[key(proxy, participant)];
    delete sessions[key(proxy, participant)];
    const back = old ? sessions[key(proxy, old)] ?? "" : "";
    if (old && key(proxy, back) === key(proxy, participant)) {
      delete sessions[key(proxy, old)];
    }
  }
  sessions[key(proxy, a)] = b;
  sessions[key(proxy, b)] = a;
  save(sessions);
  return [key(proxy, a), key(proxy, b)];
}

/** Who this participant reaches on this proxy, or undefined. */
export const otherParty = (proxy: string, participant: string | undefined) =>
  participant ? load()[key(proxy, participant)] : undefined;

const render = (s: SWMLService) =>
  JSON.parse(s.renderDocument()) as Record<string, unknown>;

/** A call to the proxy becomes a call to the other party, from the proxy. */
export function callDocument(caller: string | undefined, proxy: string) {
  const service = new SWMLService({ name: "proxy-call", route: "/call" });
  const other = otherParty(proxy, caller);
  if (other) {
    service.addVerb("connect", { to: other, from: proxy });
  } else {
    service.addVerb("answer", {});
    service.addVerb("play", { url: `say:${NOT_ACTIVE}` });
    service.addVerb("hangup", {});
  }
  return render(service);
}

/**
 * A text to the proxy becomes a text to the other party, from the proxy.
 * `reply` is the Messaging SWML method, and its `to` defaults to the sender,
 * so naming `to` is what relays the text. SWMLService validates against the
 * bundled Calling schema, which has no messaging methods, so this one is built
 * as an object.
 */
export function messageDocument(sender: string | undefined, proxy: string, body: string) {
  const other = otherParty(proxy, sender);
  const steps: Record<string, unknown>[] = [];
  if (other) steps.push({ reply: { to: other, from: proxy, body: body ?? "" } });
  // an unknown sender gets an empty document: nothing sent, nothing kept
  return { version: "1.0.0", sections: { main: steps } };
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
  });
}

/** The three routes: SignalWire posts to /call and /message, you post to /pair. */
export function serve(port: number) {
  const pairAuth = Buffer.from(`${AUTH_USER}:${AUTH_PASSWORD}`).toString("base64");
  const expected = `Basic ${pairAuth}`;
  return createServer(async (req, res) => {
    const raw = await readBody(req);
    const send = (status: number, body?: unknown,
                  headers: Record<string, string> = {}) => {
      res.writeHead(status, { "content-type": "application/json", ...headers });
      res.end(body === undefined ? "" : JSON.stringify(body));
    };
    if (req.method !== "POST") return send(404);
    let payload: Record<string, Record<string, string>> = {};
    try { payload = JSON.parse(raw); } catch { /* an empty body has no call */ }
    if (req.url === "/pair") {
      if (!ADMIN_KEY || req.headers["x-proxy-key"] !== ADMIN_KEY) return send(403);
      type PairBody = { a: string; b: string; proxy?: string };
      const { a, b, proxy } = payload as unknown as PairBody;
      return send(200, { keys: pair(a, b, proxy ?? PROXY) });
    }
    if (req.url === "/call" || req.url === "/message") {
      if (!AUTH_USER || req.headers.authorization !== expected) {
        return send(401, undefined, { "www-authenticate": 'Basic realm="proxy"' });
      }
      if (req.url === "/call") {
        const c = payload["call"] ?? {};
        return send(200, callDocument(c["from"], c["to"] ?? PROXY));
      }
      const m = payload["message"] ?? {};
      return send(200, messageDocument(m["from"], m["to"] ?? PROXY, m["body"] ?? ""));
    }
    send(404);
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const [name, value] of Object.entries({ SWML_BASIC_AUTH_USER: AUTH_USER,
      SWML_BASIC_AUTH_PASSWORD: AUTH_PASSWORD, PROXY_ADMIN_KEY: ADMIN_KEY })) {
    if (!value) throw new Error(`${name} is required; see .env.example`);
  }
  serve(Number(process.env["PORT"] ?? 8080));
  console.log("listening: POST /call, POST /message, POST /pair");
}
