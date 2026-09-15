/**
 * Run the same voice AI agent over text chat.
 *
 * The agent below is the one a phone number reaches. The AI Chat API reaches
 * it too: `POST /api/ai/chat` takes a JSON-RPC 2.0 body whose
 * `params.config_url` is the URL this agent serves its SWML from, and
 * SignalWire fetches the definition server-to-server. One request is one
 * turn. Six methods travel over the one endpoint: `create_conversation`,
 * `chat`, `end_conversation`, `delete`, `chat_log` and `summarize`.
 *
 * `@signalwire/sdk` 2.0.5 wraps no method for this path, so the requests go
 * through the client's HTTP layer directly.
 *
 * Written against @signalwire/sdk 2.0.5 (AgentBase, RestClient).
 *
 *     npm start serve     # the agent, at /front-desk/ behind basic auth
 *     npm start chat      # a text conversation with it, from your terminal
 */
import "dotenv/config";
import { randomUUID } from "node:crypto";
import { createInterface } from "node:readline/promises";
import { AgentBase, RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();
type Http = { post(path: string, body: unknown): Promise<Envelope> };
const http = (client.chat as unknown as { _http: Http })._http;

export const CHAT = "/api/ai/chat";
export const ROUTE = "/front-desk";
export const ROLES = ["user", "system"] as const;   // the spec's enum for params.role
type Role = (typeof ROLES)[number];

type Envelope = {
  jsonrpc: "2.0"; id: string;
  result?: Record<string, unknown>;
  error?: { code?: number; message?: string } | null;
};

/** The agent a phone call reaches. Nothing here is chat-specific. */
export class FrontDesk extends AgentBase {
  constructor() {
    super({ name: "front-desk", route: ROUTE });
    this.promptAddSection("Role", { body: "You answer for Ridgeline Cycles, a bike shop. "
                                          + "Be brief and warm." });
    this.promptAddSection("Hours", { body: "Open Monday to Friday, nine to five, "
                                           + "Eastern time. Closed weekends." });
    this.promptAddSection("Limits", { body: "You cannot book repairs. Offer the shop "
                                            + "number for that." });
    this.setPostPrompt("Summarise the conversation in one sentence.");
  }
}

/**
 * Where the platform fetches the agent's SWML: this agent's route, with a
 * trailing slash, on your public host, carrying the basic-auth pair. The
 * platform gets only the URL, so the credentials travel inside it.
 */
export function configUrl(agent: AgentBase, publicBase?: string) {
  const base = new URL(publicBase ?? process.env["AGENT_PUBLIC_URL"] ?? "");
  const [user, password] = agent.getBasicAuthCredentials();
  base.username = encodeURIComponent(user);
  base.password = encodeURIComponent(password);
  base.pathname = base.pathname.replace(/\/$/, "") + agent.route + "/";
  base.search = "";
  return base.toString();
}

/**
 * A JSON-RPC error. It arrives inside an HTTP 200, so the HTTP layer never
 * throws for it; `code` is the service's number (-32001 is an unknown
 * conversation, -32002 an unreachable config_url).
 */
export class ChatError extends Error {
  constructor(public code: number | null, message: string) {
    super(`${code}: ${message}`);
  }
}

/** The six methods, each one POST with a JSON-RPC 2.0 envelope. */
export class TextChannel {
  constructor(private readonly transport: Http = http) {}

  async rpc(method: string, params: Record<string, unknown>) {
    const envelope = await this.transport.post(CHAT, {
      jsonrpc: "2.0", id: randomUUID().replace(/-/g, ""), method, params,
    });
    if ("error" in envelope) {
      const err = envelope.error ?? {};
      throw new ChatError(err.code ?? null, err.message ?? "");
    }
    return envelope.result ?? {};
  }

  /** A conversation you name. `initial_message` carries the agent's opening line. */
  create(cid: string, url: string, userMessage?: string, timeout?: number) {
    const params: Record<string, unknown> = { id: cid, config_url: url };
    if (userMessage) params["user_message"] = userMessage;
    if (timeout) params["conversation_timeout"] = timeout;
    return this.rpc("create_conversation", params);
  }

  /** One turn. A `system` message steers the agent without appearing as the user. */
  say(cid: string, message: string, role: Role = "user") {
    if (!ROLES.includes(role)) {
      throw new Error(`role must be one of ${ROLES.join(", ")}, not '${role}'`);
    }
    const params: Record<string, unknown> = { id: cid, message };
    if (role !== "user") params["role"] = role;
    return this.rpc("chat", params);
  }

  async log(cid: string) {
    return ((await this.rpc("chat_log", { id: cid }))["chat_log"] ?? []) as unknown[];
  }

  /** A summary on demand. A failure rides the success envelope as `error`. */
  async summarize(cid: string, prompt?: string) {
    const params: Record<string, unknown> = { id: cid };
    if (prompt) params["summary_prompt"] = prompt;
    const result = await this.rpc("summarize", params);
    if (!("summary" in result)) {
      throw new ChatError(null, String(result["error"] ?? "no summary produced"));
    }
    return result["summary"] as string;
  }

  /** Ends the conversation and runs post-processing (the post_prompt). */
  end(cid: string) { return this.rpc("end_conversation", { id: cid }); }

  /** Removes the conversation with no post-processing. */
  delete(cid: string) { return this.rpc("delete", { id: cid }); }
}

/** A terminal conversation: create, turns until 'bye', then end. */
export async function converse(channel: TextChannel, url: string) {
  const cid = "text-" + randomUUID().replace(/-/g, "");
  const rl = createInterface({ input: process.stdin, output: process.stdout });
  const made = await channel.create(cid, url);
  if (made["initial_message"]) console.log("agent:", made["initial_message"]);
  for (;;) {
    const text = (await rl.question("you: ")).trim();
    if (!text || text.toLowerCase() === "bye") break;
    console.log("agent:", (await channel.say(cid, text))["response"]);
  }
  console.log("summary:", await channel.summarize(cid));
  await channel.end(cid);
  rl.close();
}

export const agent = new FrontDesk();

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd] = process.argv.slice(2);
  if (cmd === "serve") {
    await agent.serve({ port: Number(process.env["PORT"] ?? 3000) });
  } else if (cmd === "chat") {
    await converse(new TextChannel(), configUrl(agent));
  } else {
    console.log("usage: npm start serve | npm start chat");
  }
}
