/**
 * Transfer a SIP call with REFER.
 *
 * The spec's command table describes `calling.refer` as "Transfer a SIP call
 * via SIP REFER". The command takes a `device`, and the device takes a `type`
 * of `sip`, the only value the enum holds, and `params` whose `to` must be a
 * `sip:` URI. Optional credentials go with it when the far end challenges the
 * REFER.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start refer <call_id> sip:desk-2@pbx.example.com
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// the only device type the spec's enum holds
export const DEVICE_TYPE = "sip";

// credentials for a far end that challenges the REFER
export const SIP_USERNAME = process.env["SIP_REFER_USERNAME"] ?? "";
export const SIP_PASSWORD = process.env["SIP_REFER_PASSWORD"] ?? "";

function sipUri(value: string, field: string) {
  if (!value.startsWith("sip:")) {
    throw new Error(`${field} must be a sip: URI, not '${value}'`);
  }
  return value;
}

/** Ask the far SIP end to transfer the call to `to`. */
export function refer(callId: string, to: string, fromUri?: string,
                      statusUrl?: string) {
  const params: Record<string, string> = { to: sipUri(to, "to") };
  if (fromUri) {
    // the spec: optional, and a sip: URI when it is there
    params["from"] = sipUri(fromUri, "from");
  }
  if (SIP_USERNAME && SIP_PASSWORD) {
    params["username"] = SIP_USERNAME;
    params["password"] = SIP_PASSWORD;
  }
  const body: Record<string, unknown> = {
    device: { type: DEVICE_TYPE, params },
  };
  if (statusUrl) {
    // refer lifecycle webhooks land here
    body["status_url"] = statusUrl;
  }
  return client.calling.refer(callId, body);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, to] = process.argv.slice(2);
  if (!callId || cmd !== "refer") {
    console.log("usage: npm start refer <call_id> sip:someone@example.com");
  } else {
    console.log(await refer(callId, to));
  }
}
