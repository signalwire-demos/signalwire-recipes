/**
 * The recorder verify.py drives. On a real port it posts the inbound message
 * payloads verify.py hands it, then one without credentials and one missing
 * the required fields, and prints every document and status as JSON.
 * Expected values live in verify.py.
 */
import { request } from "node:http";

const recipe = await import("./index.js");
type Json = Record<string, unknown>;
type Case = { from: string; to: string; body: string };
const cases = JSON.parse(process.argv[2] ?? "[]") as Case[];
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");

const server = recipe.serve(0);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;

const inbound = (c: Case) => ({
  message: { message_id: "m-1", project_id: "proj-1234", space_id: "sp-1",
             direction: "inbound", type: "sms", from: c.from, to: c.to, body: c.body,
             media: [], segments: 1, timestamp: "2026-09-05T09:00:00Z" },
  vars: {}, params: {},
});

function post(body: unknown, headers: Record<string, string>) {
  return new Promise<{ status: number; json: unknown }>((resolve, reject) => {
    const req = request(`http://127.0.0.1:${port}/inbound`, { method: "POST",
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

const results: Json[] = [];
for (const c of cases) {
  results.push((await post(inbound(c), { Authorization: auth })).json as Json);
}
const unauthorized = (await post(inbound(cases[0]!), {})).status;
const incomplete = (await post({ message: { body: "hi" } },
                               { Authorization: auth })).status;
server.close();
console.log(JSON.stringify({ results, unauthorized, incomplete }));
