/**
 * The recorder verify.py drives. It captures the client's fetch, serves the
 * handler on a real port and a temporary marker directory, posts the signed
 * events verify.py hands it plus refusals, and prints what was captured. It
 * also reports the URL the signature would be over for a tagged query, so
 * verify.py can hold both surfaces to the same rule.
 */
import { createHmac } from "node:crypto";
import { mkdtempSync, readdirSync } from "node:fs";
import { request } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";

type Captured = { method: string; path: string; body: unknown };
const captured: Captured[] = [];
const marksAtDial: number[] = [];
const events = JSON.parse(process.argv[2] ?? "[]") as Record<string, unknown>[];
// the sentinel recipient stands for a dial whose response never arrives
const FAIL_TO = "+14155559999";
let calls = 0;

const scratch = mkdtempSync(join(tmpdir(), "fallback-"));
const handledDir = join(scratch, "handled");
process.env["HANDLED_DIR"] = handledDir;

// HttpClient captures globalThis.fetch when the client is built, so it is
// replaced before index.ts is imported
globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
  const params = (body as { params?: { to?: string } } | null)?.params;
  if (params?.to === FAIL_TO) throw new Error("the response never arrived");
  // the id must already be claimed by the time the dial goes out
  marksAtDial.push(readdirSync(handledDir).length);
  captured.push({ method: init?.method ?? "GET",
                  path: new URL(String(input)).pathname, body });
  calls += 1;
  return new Response(JSON.stringify({ id: `call-${calls}` }), {
    status: 200, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

const recipe = await import("./index.js");
const key = process.env["SIGNALWIRE_SIGNING_KEY"] ?? "";

const server = recipe.serve(0);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;

function post(path: string, raw: string, headers: Record<string, string>) {
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
    req.end(raw);
  });
}

const sign = (algorithm: string, raw: string, query = "") =>
  createHmac(algorithm, key).update(recipe.signedUrl(query) + raw).digest("hex");

const answers: unknown[] = [];
for (const event of events) {
  const raw = JSON.stringify(event);
  const res = await post(recipe.STATUS_PATH, raw,
                         { "X-Signalwire-Signature": sign("sha1", raw) });
  answers.push(res.json);
}

const one = JSON.stringify(events[0]);
// a SHA-256 header is preferred, and an empty one beside a valid SHA-1 fails
const sha256 = (await post(recipe.STATUS_PATH, one, {
  "X-Signalwire-SHA256-Signature": sign("sha256", one),
})).status;
const emptySha256 = (await post(recipe.STATUS_PATH, one, {
  "X-Signalwire-SHA256-Signature": "",
  "X-Signalwire-Signature": sign("sha1", one),
})).status;
const unsigned = (await post(recipe.STATUS_PATH, one, {})).status;
const badSig = (await post(recipe.STATUS_PATH, one,
                           { "X-Signalwire-Signature": "00" })).status;
// a request carrying a query is signed over the URL with that query
const tagged = (await post(`${recipe.STATUS_PATH}?token=abc`, one, {
  "X-Signalwire-Signature": sign("sha1", one, "token=abc"),
})).status;
// the signature covers the raw query: an encoded space must survive it
const encoded = (await post(`${recipe.STATUS_PATH}?tag=a%20b`, one, {
  "X-Signalwire-Signature": sign("sha1", one, "tag=a%20b"),
})).status;
// A dial whose response never arrives is a 500 the platform can retry, and
// the server stays up: the retry is answered, and it finds the claim.
const boomRaw = JSON.stringify({ ...(events[0] ?? {}), id: "m-11", to: FAIL_TO });
const boomSig = { "X-Signalwire-Signature": sign("sha1", boomRaw) };
const failed = (await post(recipe.STATUS_PATH, boomRaw, boomSig)).status;
const retry = await post(recipe.STATUS_PATH, boomRaw, boomSig);
server.close();
console.log(JSON.stringify({ captured, answers, marksAtDial, sha256, emptySha256,
                             unsigned, badSig, tagged, encoded, failed,
                             alive: retry.status, afterFailure: retry.json,
                             signedUrlTagged: recipe.signedUrl("token=abc") }));
