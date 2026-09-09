/**
 * The recorder verify.py drives. On a real port and a temporary sessions file
 * it tries /pair without and with the key, then posts the inbound call and
 * inbound message payloads for both parties and a stranger, then posts without
 * credentials, and prints every document and status as JSON.
 */
import { mkdtempSync } from "node:fs";
import { request } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";

process.env["SESSIONS_PATH"] = join(mkdtempSync(join(tmpdir(), "proxy-")), "sessions.json");
const recipe = await import("./index.js");
const [alice = "", bob = "", stranger = "", text = "", carol = "", aliceSpelled = "",
       dave = ""] = process.argv.slice(2);
const proxy = process.env["PROXY_NUMBER"] ?? "";
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");
const adminKey = process.env["PROXY_ADMIN_KEY"] ?? "";

const server = recipe.serve(0);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;

const inboundCall = (from: string) => ({
  call: { call_id: "c-1", node_id: "n", segment_id: "s", call_state: "created",
          direction: "inbound", type: "phone", from, to: proxy, headers: [],
          project_id: "proj-1234", space_id: "sp-1" },
  vars: {}, envs: {}, params: {},
});
const inboundText = (from: string) => ({
  message: { message_id: "m-1", project_id: "proj-1234", space_id: "sp-1",
             direction: "inbound", type: "sms", from, to: proxy, body: text, media: [],
             segments: 1, timestamp: "2026-09-05T09:00:00Z" },
  vars: {}, params: {},
});

function post(path: string, body: unknown, headers: Record<string, string>) {
  return new Promise<{ status: number; json: unknown }>((resolve, reject) => {
    const req = request(`http://127.0.0.1:${port}${path}`, { method: "POST",
      headers: { "content-type": "application/json", ...headers } }, (res) => {
      const chunks: Buffer[] = [];
      res.on("data", (c: Buffer) => chunks.push(c));
      res.on("end", () => {
        const t = Buffer.concat(chunks).toString();
        resolve({ status: res.statusCode ?? 0, json: t ? JSON.parse(t) : null });
      });
    });
    req.on("error", reject);
    req.end(JSON.stringify(body));
  });
}

const pairBody = { a: alice, b: bob };
const pairRes = {
  noKey: (await post("/pair", pairBody, {})).status,
  wrongKey: (await post("/pair", pairBody, { "X-Proxy-Key": "nope" })).status,
  withKey: (await post("/pair", pairBody, { "X-Proxy-Key": adminKey })).status,
};
const A = { Authorization: auth };
const call = {
  alice: (await post("/call", inboundCall(alice), A)).json,
  bob: (await post("/call", inboundCall(bob), A)).json,
  stranger: (await post("/call", inboundCall(stranger), A)).json,
};
const textDocs = {
  alice: (await post("/message", inboundText(alice), A)).json,
  bob: (await post("/message", inboundText(bob), A)).json,
  stranger: (await post("/message", inboundText(stranger), A)).json,
};
const unauthorized = {
  call: (await post("/call", inboundCall(alice), {})).status,
  message: (await post("/message", inboundText(alice), {})).status,
};
// re-pairing Alice with Carol removes Bob's route back to her
await post("/pair", { a: alice, b: carol }, { "X-Proxy-Key": adminKey });
const repaired = {
  alice: (await post("/call", inboundCall(alice), A)).json,
  carol: (await post("/call", inboundCall(carol), A)).json,
  bob: (await post("/call", inboundCall(bob), A)).json,
  bobText: (await post("/message", inboundText(bob), A)).json,
};
// the same number spelled differently is the same participant
await post("/pair", { a: aliceSpelled, b: dave }, { "X-Proxy-Key": adminKey });
const respelled = {
  alice: (await post("/call", inboundCall(alice), A)).json,
  carol: (await post("/call", inboundCall(carol), A)).json,
};
server.close();
console.log(JSON.stringify({ pair: pairRes, call, text: textDocs, unauthorized, repaired,
                             respelled }));
