/**
 * The recorder verify.py drives. It starts the server on a real port, posts the
 * inbound-call payload with and without a caller id, then without credentials,
 * and prints the two documents and the status as JSON.
 */
import { request } from "node:http";

const recipe = await import("./index.js");
const [caller = ""] = process.argv.slice(2);
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");

const server = recipe.serve(0);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;

const inbound = (from?: string) => ({
  call: { call_id: "c-1", node_id: "n", segment_id: "s", call_state: "created",
          direction: "inbound", type: "phone", to: "+15551230000", headers: [],
          project_id: "proj-1234", space_id: "sp-1", ...(from === undefined ? {} : { from }) },
  vars: {}, envs: {}, params: {},
});

function post(body: unknown, headers: Record<string, string>) {
  return new Promise<{ status: number; json: unknown }>((resolve, reject) => {
    const req = request(`http://127.0.0.1:${port}/swml`, { method: "POST",
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

const withCaller = await post(inbound(caller), { Authorization: auth });
const anonymous = await post(inbound(undefined), { Authorization: auth });
const unauthorized = await post(inbound(caller), {});
server.close();

console.log(JSON.stringify({ withCaller: withCaller.json, anonymous: anonymous.json,
                             unauthorized: unauthorized.status }));
