/**
 * The recorder verify.py drives. It renders the document for two callers
 * through the agent's own app, saves a summary through the post-prompt handler
 * on a real port, asks for it back, asks for an unknown caller, tries without
 * credentials, and prints all of it as JSON.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's behaviour to the same one set.
 */
import { mkdtempSync } from "node:fs";
import { request } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";

process.env["MEMORY_PATH"] = join(mkdtempSync(join(tmpdir(), "memory-")), "caller-memory.json");
const recipe = await import("./index.js");
const [dana = "", lee = "", danaSummary = ""] = process.argv.slice(2);
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");

const agent = new recipe.FrontDesk();
const app = agent.getApp();
const swmlRequest = (from: string) => ({
  call: { call_id: "c-1", node_id: "n", segment_id: "s", call_state: "created",
          direction: "inbound", type: "phone", from, to: "+15551230000", headers: [],
          project_id: "proj-1234", space_id: "sp-1" },
  vars: {}, envs: {}, params: {},
});
type Doc = { sections: { main: Record<string, Record<string, unknown>>[] } };
async function render(from: string) {
  const res = await app.fetch(new Request("http://local/front-desk/", {
    method: "POST", headers: { Authorization: auth, "content-type": "application/json" },
    body: JSON.stringify(swmlRequest(from)),
  }));
  const doc = (await res.json()) as Doc;
  return doc.sections.main.find((s) => "ai" in s)!["ai"] as Record<string, unknown>;
}
const ai = await render(dana);
const ai2 = await render(lee);
const ai4 = await render("anonymous");

// the handler on a real port, exactly as the platform would reach it
const server = recipe.servePostPrompt(0);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;

function post(body: unknown, headers: Record<string, string>) {
  return new Promise<{ status: number; json: unknown }>((resolve, reject) => {
    const req = request(`http://127.0.0.1:${port}/post_prompt`, { method: "POST",
      headers: { "content-type": "application/json", ...headers } }, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => chunks.push(c));
      res.on("end", () => {
        const text = Buffer.concat(chunks).toString();
        resolve({ status: res.statusCode ?? 0, json: text ? JSON.parse(text) : null });
      });
    });
    req.on("error", reject);
    req.end(JSON.stringify(body));
  });
}
const danaId = recipe.conversationId(dana);
const saved = await post({ action: "post_conversation", conversation_id: danaId,
                           post_prompt_data: { raw: danaSummary } }, { Authorization: auth });
const fetched = await post({ action: "fetch_conversation", conversation_id: danaId },
                           { Authorization: auth });
const unknown = await post({ action: "fetch_conversation", conversation_id: "caller-000" },
                           { Authorization: auth });
const unauthorized = await post({ action: "fetch_conversation", conversation_id: danaId }, {});
server.close();

console.log(JSON.stringify({
  params: ai["params"], otherId: (ai2["params"] as Record<string, unknown>)["conversation_id"],
  postPromptUrl: ai["post_prompt_url"], anonParams: ai4["params"] ?? {},
  saved: saved.json, fetched: fetched.json,
  unknown: unknown.json, unauthorized: unauthorized.status,
}));
