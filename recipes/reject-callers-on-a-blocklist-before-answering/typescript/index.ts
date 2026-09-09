/**
 * Reject callers on a blocklist before answering.
 *
 * SignalWire fetches your document with the inbound call webhook, whose body
 * carries `call.from`. Your handler reads it and decides. A number on the list
 * gets a one-verb document, `hangup` with a reason, and no `answer` before it,
 * so the call is refused rather than picked up. Everyone else gets `answer` and
 * `connect`. The list is yours; the platform never sees it.
 *
 * Written against @signalwire/sdk 2.0.5 (SWMLService) and node:http.
 *
 *     npm start            # serves POST /swml
 */
import "dotenv/config";
import { createServer, type IncomingMessage } from "node:http";
import { SWMLService } from "@signalwire/sdk";

// where allowed callers end up; swap for your queue or agent
export const DESTINATION = process.env["DESTINATION"] ?? "+15550100001";

// the numbers to refuse, in any format; compared by digits. Swap for your table
export const BLOCKLIST = ["+15555550100", "+1 (555) 555-0101"];

// the schema's reasons are hangup, busy and decline; decline tells the far end
// the call was refused, busy makes it look like a busy line
export const REASON = process.env["REJECT_REASON"] ?? "decline";

const AUTH_USER = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const AUTH_PASSWORD = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";

/** +1 (555) 555-0101 and 15555550101 are the same caller. */
export const digits = (number: string | undefined) => (number ?? "").replace(/\D/g, "");

const BLOCKED = new Set(BLOCKLIST.map(digits));

/** True for a listed number. An absent caller id is not on any list. */
export function isBlocked(caller: string | undefined): boolean {
  const d = digits(caller);
  return d.length > 0 && BLOCKED.has(d);
}

/** The SWML for this caller: refused before answering, or answered and connected. */
export function document(caller: string | undefined): Record<string, unknown> {
  const service = new SWMLService({ name: "screen", route: "/swml" });
  if (isBlocked(caller)) {
    // no answer verb: the call is declined, not picked up and dropped
    service.addVerb("hangup", { reason: REASON });
  } else {
    service.addVerb("answer", {});
    service.addVerb("connect", { to: DESTINATION });
  }
  return JSON.parse(service.renderDocument());
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => resolve(Buffer.concat(chunks).toString()));
  });
}

/** POST /swml, behind the basic auth SignalWire is given in the webhook URL. */
export function serve(port: number) {
  const pair = Buffer.from(`${AUTH_USER}:${AUTH_PASSWORD}`).toString("base64");
  const expected = `Basic ${pair}`;
  return createServer(async (req, res) => {
    const raw = await readBody(req);
    if (req.method !== "POST" || !req.url?.startsWith("/swml")) {
      res.writeHead(404);
      return res.end();
    }
    if (!AUTH_USER || req.headers.authorization !== expected) {
      res.writeHead(401, { "www-authenticate": 'Basic realm="swml"' });
      return res.end();
    }
    let payload: { call?: { from?: string } } = {};
    try { payload = JSON.parse(raw); } catch { /* no call, no caller */ }
    res.writeHead(200, { "content-type": "application/json" });
    res.end(JSON.stringify(document(payload.call?.from)));
  }).listen(port);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  if (!AUTH_USER || !AUTH_PASSWORD) {
    throw new Error("SWML_BASIC_AUTH_USER and SWML_BASIC_AUTH_PASSWORD are required; "
                    + "see .env.example");
  }
  serve(Number(process.env["PORT"] ?? 8080));
  console.log("listening: POST /swml");
}
