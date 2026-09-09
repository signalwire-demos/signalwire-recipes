/**
 * Forward calls to a phone and keep the caller's number.
 *
 * A forwarded call usually shows the forwarding number on the phone that rings,
 * so whoever answers cannot see who is really calling. `connect` takes a `from`,
 * which the bundled schema describes as "the caller ID to use when dialing the
 * number". Set it to the inbound `call.from` and the forwarded phone shows the
 * original caller.
 *
 * Written against @signalwire/sdk 2.0.5 (SWMLService) and node:http.
 *
 *     npm start            # serves POST /swml
 */
import "dotenv/config";
import { createServer, type IncomingMessage } from "node:http";
import { SWMLService } from "@signalwire/sdk";

// the phone that should ring; swap for your on-call rota
export const FORWARD_TO = process.env["FORWARD_TO"] ?? "+15550100001";
export const RING_FOR = Number(process.env["RING_FOR"] ?? 25);

const AUTH_USER = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const AUTH_PASSWORD = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";

/** Connect to the forwarding target, presenting the caller's own number. */
export function document(caller: string | undefined): Record<string, unknown> {
  const service = new SWMLService({ name: "forward", route: "/swml" });
  const connect: Record<string, unknown> = { to: FORWARD_TO, timeout: RING_FOR };
  if (caller) {
    // the caller ID the ringing phone displays. Without a caller id the
    // platform picks, so the key is left out rather than set to nothing
    connect["from"] = caller;
  }
  service.addVerb("connect", connect);
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
