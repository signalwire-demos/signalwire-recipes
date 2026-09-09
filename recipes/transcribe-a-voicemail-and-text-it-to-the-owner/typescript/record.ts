/**
 * The recorder verify.py drives. It captures the client's fetch, serves both
 * routes on a real port and a temporary seen file, fetches the voicemail
 * document, posts the signed transcription callbacks verify.py hands it plus
 * one unsigned, and prints what was captured. Expected values live in verify.py.
 */
import { createHmac } from "node:crypto";
import { mkdtempSync } from "node:fs";
import { request } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";

type Captured = { method: string; path: string; body: unknown };
const captured: Captured[] = [];
const [caller = ""] = process.argv.slice(2);
const events = JSON.parse(process.argv[3] ?? "[]") as Record<string, string>[];
// the sentinel body stands for a send whose response never arrives
const FAIL_MARK = "the response never arrived";
let sent = 0;

// HttpClient captures globalThis.fetch when the client is built, so it is
// replaced before index.ts is imported
globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const body = typeof init?.body === "string" ? JSON.parse(init.body) : null;
  const text = String((body as { Body?: string } | null)?.Body ?? "");
  if (text.includes(FAIL_MARK)) throw new Error(FAIL_MARK);
  sent += 1;
  captured.push({ method: init?.method ?? "GET",
                  path: new URL(String(input)).pathname, body });
  return new Response(JSON.stringify({ sid: `SM${sent}` }), {
    status: 200, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

const scratch = mkdtempSync(join(tmpdir(), "voicemail-"));
process.env["SEEN_DIR"] = join(scratch, "seen");
const recipe = await import("./index.js");
const key = process.env["SIGNALWIRE_SIGNING_KEY"] ?? "";

const server = recipe.serve(0);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;

function post(path: string, raw: string, headers: Record<string, string>) {
  return new Promise<{ status: number; text: string }>((resolve, reject) => {
    const req = request(`http://127.0.0.1:${port}${path}`, { method: "POST", headers },
      (res) => {
        const chunks: Buffer[] = [];
        res.on("data", (c: Buffer) => chunks.push(c));
        res.on("end", () => resolve({ status: res.statusCode ?? 0,
                                      text: Buffer.concat(chunks).toString() }));
      });
    req.on("error", reject);
    req.end(raw);
  });
}

const form = (o: Record<string, string>) => new URLSearchParams(o).toString();
const FORM = { "content-type": "application/x-www-form-urlencoded" };

const document = (await post("/voice", form({ From: caller, To: "+15551230000" }),
                             FORM)).text;
const path = `/transcription?from=${encodeURIComponent(caller)}`;
const url = recipe.PUBLIC_URL + path;
const sign = (raw: string) => createHmac("sha1", key).update(url + raw).digest("hex");

const answers: unknown[] = [];
for (const event of events) {
  const raw = form(event);
  const res = await post(path, raw, { ...FORM, "X-Signalwire-Signature": sign(raw) });
  answers.push(JSON.parse(res.text));
}
const unsigned = (await post(path, form(events[0]!), FORM)).status;
// A send whose response never arrives is a 500 the platform can retry, and
// the server stays up: the retry is answered, and it finds the claim.
const boomRaw = form({ ...(events[0] ?? {}), TranscriptionSid: "TR9",
                       TranscriptionText: FAIL_MARK });
const boomSig = { ...FORM, "X-Signalwire-Signature": sign(boomRaw) };
const failed = (await post(path, boomRaw, boomSig)).status;
const retry = await post(path, boomRaw, boomSig);
server.close();
console.log(JSON.stringify({ document, captured, answers, unsigned, failed,
                             alive: retry.status,
                             afterFailure: JSON.parse(retry.text) }));
