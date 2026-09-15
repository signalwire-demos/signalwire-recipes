/**
 * Put an AI agent in a web chat widget.
 *
 * A page cannot hold a SignalWire API token: the token carries the whole
 * project. This gateway holds it, and the page learns two things, the
 * gateway's URL and a publishable key. The gateway injects `config_url`
 * itself, so a visitor cannot pick which agent runs; it signs a handle per
 * conversation, so an id cannot be forged or guessed; and it caps new
 * conversations per window and turns per conversation, which bounds what a
 * leaked key can cost.
 *
 * The wire is modelled on the Python SDK's `ChatGateway`: `POST /chat/` with
 * the key in `Authorization: Bearer`, a `method` of `start`, `chat`, `log` or
 * `end`, and an `X-Chat-Handle` header on the response that minted the
 * handle. Upstream, every method is one JSON-RPC 2.0 POST to `/api/ai/chat`.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient) and node:http.
 *
 *     npm start          # the page at /, the gateway at /chat/
 */
import "dotenv/config";
import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();
type Envelope = {
  result?: Record<string, unknown>; error?: { code?: number; message?: string };
};
type Http = { post(path: string, body: unknown): Promise<Envelope> };
const http = (client.chat as unknown as { _http: Http })._http;

export const CHAT = "/api/ai/chat";
const env = (name: string) => {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required; see .env.example`);
  return value;
};
/** A cap that fails to parse would disable itself: `NaN >= n` is always false. */
const num = (name: string, fallback: number) => {
  const raw = process.env[name];
  const value = raw === undefined ? fallback : Number(raw);
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error(`${name} must be a positive number, not '${raw}'`);
  }
  return value;
};
// the agent this gateway may talk to; never accepted from the request
export const CONFIG_URL = env("AGENT_CONFIG_URL");
export const KEY = env("CHAT_GATEWAY_KEY");                 // the page carries this
const SECRET = env("CHAT_GATEWAY_SECRET");                  // the page never sees this
const ALLOWED_ORIGINS = new Set((process.env["ALLOWED_ORIGINS"] ?? "")
  .split(",").map((o) => o.trim()).filter(Boolean));
const MAX_NEW = num("MAX_NEW_CONVERSATIONS", 60);
const WINDOW = num("WINDOW_SECONDS", 60);
const MAX_TURNS = num("MAX_TURNS", 200);
export const TIMEOUT = num("CONVERSATION_TIMEOUT", 1800);
export const MAX_BODY = 16 * 1024;   // a chat message, not an upload
const PAGE = readFileSync(new URL("../../web/widget.html", import.meta.url), "utf-8");
const VISIBLE_ROLES = new Set(["user", "assistant"]);   // never the prompt or tools

// counters live in this process; behind replicas each keeps its own
const mints: number[] = [];
export const turns = new Map<string, { used: number; last: number }>();

/** One JSON-RPC 2.0 request. An error arrives inside an HTTP 200. */
export async function rpc(method: string, params: Record<string, unknown>,
                          transport: Http = http) {
  const envelope = await transport.post(CHAT, {
    jsonrpc: "2.0", id: randomUUID().replace(/-/g, ""), method, params,
  });
  if ("error" in envelope) {
    const err = envelope.error ?? {};
    throw new Error(`${err.code}: ${err.message ?? ""}`);
  }
  return envelope.result ?? {};
}

const sign = (cid: string) =>
  createHmac("sha256", SECRET).update(cid).digest("hex").slice(0, 32);

/** A fresh conversation id and the handle that proves this server made it. */
export function mintHandle() {
  const cid = "chat-" + randomUUID().replace(/-/g, "");
  return { cid, handle: `${cid}.${sign(cid)}` };
}

/** The conversation id inside a handle, or null when it was not ours. */
export function readHandle(handle: unknown) {
  if (typeof handle !== "string") return null;
  const at = handle.lastIndexOf(".");
  if (at < 1) return null;
  const cid = handle.slice(0, at);
  const sig = Buffer.from(handle.slice(at + 1));
  const want = Buffer.from(sign(cid));
  return sig.length === want.length && timingSafeEqual(sig, want) ? cid : null;
}

/** Coarse on purpose: a finer reason lets a caller map the caps by probing. */
class Refusal extends Error {
  constructor(public status: number, public reason: string) { super(reason); }
}

function checkKey(req: IncomingMessage) {
  if (req.headers.authorization !== `Bearer ${KEY}`) throw new Refusal(401, "key");
}

function checkOrigin(req: IncomingMessage) {
  const origin = req.headers.origin;
  const local = origin?.startsWith("http://localhost")
    || origin?.startsWith("http://127.0.0.1");
  if (origin && !local && !ALLOWED_ORIGINS.has(origin)) {
    throw new Refusal(403, "origin");
  }
}

function chargeMint(now = Date.now() / 1000) {
  while (mints.length && mints[0]! < now - WINDOW) mints.shift();
  if (mints.length >= MAX_NEW) throw new Refusal(429, "limit");
  mints.push(now);
}

/**
 * Forget conversations idle past the service's own timeout, so a visitor who
 * closes the tab without `end` does not leave a counter behind forever.
 */
export function prune(now = Date.now() / 1000) {
  for (const [cid, entry] of turns) {
    if (entry.last < now - TIMEOUT) turns.delete(cid);
  }
}

function chargeTurn(cid: string, now = Date.now() / 1000) {
  prune(now);
  const used = turns.get(cid)?.used ?? 0;
  if (used >= MAX_TURNS) throw new Refusal(429, "limit");
  turns.set(cid, { used: used + 1, last: now });
}

type Body = { method?: string; handle?: unknown; message?: unknown };
type Reply = { status: number; json: unknown; headers?: Record<string, string> };

/** The gateway, as a function of the request so a test can drive it directly. */
export async function gateway(req: IncomingMessage, body: Body,
                              transport: Http = http): Promise<Reply> {
  checkKey(req);
  checkOrigin(req);
  const method = body.method ?? "chat";
  if (method === "start") {
    chargeMint();
    const { cid, handle } = mintHandle();
    const params = { id: cid, config_url: CONFIG_URL, conversation_timeout: TIMEOUT };
    const made = await rpc("create_conversation", params, transport);
    return { status: 200, headers: { "x-chat-handle": handle },
             json: { greeting: made["initial_message"] ?? null, status: made["status"],
                     timeout: TIMEOUT } };
  }
  const cid = readHandle(body.handle);
  if (!cid) throw new Refusal(403, "handle");
  if (method === "chat") {
    const message = body.message;
    if (typeof message !== "string" || !message.trim()) {
      throw new Refusal(400, "malformed");
    }
    chargeTurn(cid);
    // the visitor is always the user; a role or a config_url in the body is ignored
    return { status: 200, json: await rpc("chat", { id: cid, message }, transport) };
  }
  if (method === "log") {
    const result = await rpc("chat_log", { id: cid }, transport);
    const entries = (result["chat_log"] ?? []) as { role?: string }[];
    const messages = entries.filter((e) => VISIBLE_ROLES.has(e.role ?? ""));
    return { status: 200, json: { messages } };
  }
  if (method === "end") {
    await rpc("end_conversation", { id: cid }, transport);
    turns.delete(cid);
    return { status: 200, json: { status: "ended" } };
  }
  throw new Refusal(400, "malformed");
}

/**
 * The body, or a 413 once more than MAX_BODY bytes have arrived. Past the cap
 * the rest is drained rather than the socket destroyed, so the refusal can
 * still be written; the response then closes the connection.
 */
function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    let size = 0;
    const onData = (c: Buffer) => {
      size += c.length;
      if (size > MAX_BODY) {
        req.off("data", onData);
        req.resume();
        reject(new Refusal(413, "malformed"));
        return;
      }
      chunks.push(c);
    };
    req.on("data", onData);
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
  });
}

async function handle(req: IncomingMessage, res: ServerResponse, transport: Http) {
  if (req.method === "GET" && req.url === "/") {
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    return res.end(PAGE.replace("__CHAT_KEY__", KEY));
  }
  if (req.method !== "POST" || req.url !== "/chat/") {
    res.writeHead(404);
    return res.end();
  }
  let reply: Reply;
  try {
    // the key is checked before a byte of the body is buffered, and a declared
    // length past the cap is refused before it is read
    checkKey(req);
    if (Number(req.headers["content-length"] ?? 0) > MAX_BODY) {
      throw new Refusal(413, "malformed");
    }
    let body: Body = {};
    try { body = JSON.parse(await readBody(req) || "{}"); } catch (error) {
      if (error instanceof Refusal) throw error;   // the body was too large
      /* otherwise malformed JSON: an empty body, refused below */
    }
    reply = await gateway(req, body, transport);
  } catch (error) {
    const r = error instanceof Refusal ? error : new Refusal(502, "upstream");
    reply = { status: r.status, json: { error: r.reason } };
  }
  const headers: Record<string, string> = { "content-type": "application/json",
                                            ...(reply.headers ?? {}) };
  if (reply.status === 413) headers["connection"] = "close";   // stop reading the rest
  res.writeHead(reply.status, headers);
  res.end(JSON.stringify(reply.json));
}

/** The page and the gateway on one port. */
export function serve(port: number, transport: Http = http) {
  // a rejection that escaped would end the process; everything answers 500 instead
  return createServer((req, res) => {
    handle(req, res, transport).catch(() => {
      res.writeHead(500, { "content-type": "application/json" });
      res.end(JSON.stringify({ error: "server" }));
    });
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  serve(Number(process.env["PORT"] ?? 8080));
}
