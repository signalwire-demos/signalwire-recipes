/**
 * Remember a returning caller across calls.
 *
 * Two `ai.params` do the work. `save_conversation` makes the platform post a
 * summary of the conversation when the call ends, and `conversation_id` names
 * the conversation it belongs to. Name it after the caller's number and the
 * next call from that number can ask for the summary back: the platform POSTs
 * `action: fetch_conversation` to the `post_prompt_url`, and the response is
 * expected to carry `conversation_summary`.
 *
 * `@signalwire/sdk` 2.0.5's own post-prompt route answers every POST with
 * `{ok: true}` and discards what `onSummary` returns, so it cannot answer a
 * fetch. This surface points `post_prompt_url` at a small handler of its own,
 * which is what `setPostPromptUrl` exists for.
 *
 * Written against @signalwire/sdk 2.0.5 (AgentBase, setDynamicConfigCallback).
 *
 *     npm start          # the agent on :3000, the post-prompt handler on :3001
 */
import "dotenv/config";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage } from "node:http";
import { AgentBase } from "@signalwire/sdk";

// where each caller's last summary lives; swap for your database
export const MEMORY_PATH = process.env["MEMORY_PATH"] ?? "caller-memory.json";
// the public URL of the handler below, as the platform will call it
export const POST_PROMPT_URL = process.env["POST_PROMPT_URL"]
  ?? "http://localhost:3001/post_prompt";

const AUTH_USER = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const AUTH_PASSWORD = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";

/**
 * The platform gets only the URL, so the credentials travel inside it. They
 * are percent-encoded first: a literal % in a password would otherwise be read
 * as an escape by the client that decodes the URL before building Basic auth.
 */
export function withCredentials(url: string) {
  const u = new URL(url);
  if (!u.username) {
    u.username = encodeURIComponent(AUTH_USER);
    u.password = encodeURIComponent(AUTH_PASSWORD);
  }
  return u.toString();
}

/**
 * One conversation per caller, keyed on the digits of the number. A caller
 * with no digits (anonymous, or a SIP URI with none) gets undefined, so no
 * memory is kept rather than one memory shared by every such caller.
 */
export function conversationId(number: string | undefined) {
  const digits = (number ?? "").replace(/\D/g, "");
  return digits ? `caller-${digits}` : undefined;
}

type Memory = Record<string, string>;
const load = (): Memory =>
  existsSync(MEMORY_PATH) ? JSON.parse(readFileSync(MEMORY_PATH, "utf-8")) : {};
function save(memory: Memory) {
  writeFileSync(`${MEMORY_PATH}.tmp`, JSON.stringify(memory, null, 2), "utf-8");
  renameSync(`${MEMORY_PATH}.tmp`, MEMORY_PATH);
}

export class FrontDesk extends AgentBase {
  constructor() {
    super({ name: "front-desk", route: "/front-desk" });
    this.promptAddSection("Role", { body: "You answer the phone for Ridgeline Cycles, "
                                          + "a bike shop. Be brief and warm." });
    this.promptAddSection("Memory", {
      body: "If a summary of a previous call is available, greet the caller as "
          + "someone you have spoken to and pick up from it.",
    });
    // a post_prompt is what makes the SDK emit post_prompt_url, which
    // save_conversation needs; the summary it asks for is what gets kept
    this.setPostPrompt("Summarise the call in two sentences, including anything "
                       + "the caller asked you to remember.");
    this.setPostPromptUrl(withCredentials(POST_PROMPT_URL));
    // the SWML request body carries the call, and call.from is the caller
    this.setDynamicConfigCallback((_query, body, _headers, agent) => {
      const call = (body as { call?: { from?: string } }).call ?? {};
      const cid = conversationId(call.from);
      if (cid) {
        agent.setParams({ save_conversation: true, conversation_id: cid });
      }
    });
  }
}

type PostPromptBody = {
  action?: string; conversation_id?: string;
  post_prompt_data?: { raw?: string; parsed?: unknown[] };
};

/** Save at the end of a call; answer a fetch at the start of the next. */
export function handlePostPrompt(body: PostPromptBody): Record<string, unknown> {
  const cid = body.conversation_id ?? "";
  if (body.action === "fetch_conversation") {
    const remembered = load()[cid];
    // the platform reads conversation_summary from this response
    return remembered ? { conversation_summary: remembered } : {};
  }
  const summary = body.post_prompt_data?.raw
    ?? (body.post_prompt_data?.parsed?.[0] as string | undefined);
  if (summary && cid) {
    const memory = load();
    memory[cid] = typeof summary === "string" ? summary : JSON.stringify(summary);
    save(memory);
  }
  return { success: true };
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
  });
}

/** The post-prompt handler, behind the same basic auth the agent uses. */
export function servePostPrompt(port: number) {
  const user = AUTH_USER;
  const expected = "Basic " + Buffer.from(`${user}:${AUTH_PASSWORD}`).toString("base64");
  return createServer(async (req, res) => {
    const raw = await readBody(req);
    if (!user || req.headers.authorization !== expected) {
      res.writeHead(401, { "www-authenticate": "Basic" });
      return res.end();
    }
    let body: PostPromptBody = {};
    try { body = JSON.parse(raw); } catch { /* an empty body saves nothing */ }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(handlePostPrompt(body)));
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const name of ["SWML_BASIC_AUTH_USER", "SWML_BASIC_AUTH_PASSWORD"]) {
    if (!process.env[name]) throw new Error(`${name} is required; see .env.example`);
  }
  servePostPrompt(Number(process.env["POST_PROMPT_PORT"] ?? 3001));
  new FrontDesk().serve({ port: Number(process.env["PORT"] ?? 3000) });
}
