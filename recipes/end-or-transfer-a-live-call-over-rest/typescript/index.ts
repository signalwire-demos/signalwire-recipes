/**
 * End or transfer a live call over REST.
 *
 * Three call commands, each one POST to /api/calling/calls addressed to a call
 * id: `calling.end` hangs up with a reason, `calling.transfer` moves the call to
 * a new destination, and `calling.disconnect` unbridges two connected calls.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start end <call_id> [reason]
 *     npm start transfer <call_id> <dest>
 *     npm start disconnect <call_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// the spec's enum for calling.end; anything else is refused before it is sent
export const END_REASONS = [
  "hangup", "cancel", "busy", "noAnswer", "decline", "error",
] as const;
export type EndReason = (typeof END_REASONS)[number];

/** End the call. `reason` is what the far end and the logs see. */
export function hangUp(callId: string, reason: EndReason = "hangup") {
  if (!END_REASONS.includes(reason)) {
    throw new Error(`reason must be one of ${END_REASONS.join(", ")}, not ${reason}`);
  }
  return client.calling.end(callId, { reason });
}

/**
 * Send the call somewhere else. The spec's `dest` is a string or an object, so
 * a phone number, a SIP URI, a SWML URL or an inline SWML document all fit.
 */
export type Dest = string | Record<string, unknown>;

export function transfer(callId: string, dest: Dest) {
  return client.calling.transfer(callId, { dest });
}

/** Separate this call from its peer. The spec hangs up neither leg. */
export function unbridge(callId: string) {
  return client.calling.disconnect(callId);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, ...rest] = process.argv.slice(2);
  if (!callId) {
    console.log("usage: npm start <end|transfer|disconnect> <call_id> [reason|dest]");
  } else if (cmd === "end") {
    console.log(await hangUp(callId, (rest[0] as EndReason) ?? "hangup"));
  } else if (cmd === "transfer") {
    console.log(await transfer(callId, rest[0]));
  } else if (cmd === "disconnect") {
    console.log(await unbridge(callId));
  }
}
