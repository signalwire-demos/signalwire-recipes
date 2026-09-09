/**
 * Pause a voice AI agent mid-call and bring it back.
 *
 * `calling.ai_hold` puts the caller on hold and stops the agent listening;
 * `calling.ai_unhold` brings it back; `calling.ai.stop` ends the AI on the call
 * and leaves the call itself up.
 *
 * The spec is explicit that `ai_hold`'s `timeout` is a numeric string, and that
 * an integer payload is rejected, so this converts it and refuses anything that
 * is not a whole number of seconds.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start hold <call_id> [seconds]
 *     npm start unhold <call_id>
 *     npm start stop <call_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// what the agent says before the hold music starts
export const HOLD_PROMPT = "Let me check that for you. One moment.";

/** Hold the caller for `seconds`, after the agent says `prompt`. */
export function hold(callId: string, seconds = 90, prompt = HOLD_PROMPT) {
  if (!Number.isInteger(seconds)) {
    throw new Error(`seconds must be a whole number, not ${seconds}`);
  }
  // the spec: a numeric string. An integer payload is rejected
  return client.calling.aiHold(callId, { timeout: String(seconds), prompt });
}

/** Take the caller off hold. The agent is listening again. */
export function unhold(callId: string) {
  return client.calling.aiUnhold(callId);
}

/** End the AI on this call. The call itself stays up. */
export function stop(callId: string) {
  // the method is aiStop; the command on the wire is calling.ai.stop
  return client.calling.aiStop(callId);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, seconds] = process.argv.slice(2);
  if (!callId) {
    console.log("usage: npm start <hold|unhold|stop> <call_id> [seconds]");
  } else if (cmd === "hold") {
    console.log(await hold(callId, seconds ? Number(seconds) : undefined));
  } else if (cmd === "unhold") {
    console.log(await unhold(callId));
  } else if (cmd === "stop") {
    console.log(await stop(callId));
  }
}
