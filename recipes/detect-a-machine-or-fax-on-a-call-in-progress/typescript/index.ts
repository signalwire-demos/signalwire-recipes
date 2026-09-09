/**
 * Detect a machine, fax tone or digits on a call in progress.
 *
 * `calling.detect` starts detection on a call that is already up, from outside
 * the call's document. The `detect` object picks what to listen for: `machine`,
 * `fax` or `digit`. The result arrives at your `status_url`, so a detect
 * without one is refused here before it is sent. `calling.detect.stop` gives up
 * early.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start machine <call_id> <status_url>
 *     npm start stop <call_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// one id names this detection, and stop names it again
export const CONTROL_ID = "screening";

// the spec's three detection types
export const TYPES = ["machine", "fax", "digit"] as const;

function needsStatusUrl(statusUrl: string | undefined): asserts statusUrl is string {
  // the result arrives only by webhook; without one the detect is unobservable
  if (!statusUrl) {
    throw new Error("a detect needs a status_url to deliver its result");
  }
}

/** Answering machine detection, with the thresholds spelled out. */
export function machine(callId: string, statusUrl?: string, timeout = 30,
                        controlId = CONTROL_ID) {
  needsStatusUrl(statusUrl);
  const params = {
    machine_voice_threshold: 1.25, machine_words_threshold: 6,
    detect_message_end: true,
  };
  return client.calling.detect(callId, {
    control_id: controlId, detect: { type: "machine", params },
    timeout, status_url: statusUrl,
  });
}

/** Fax tone detection. CED is the answering tone, CNG the calling tone. */
export function fax(callId: string, statusUrl?: string, tone = "CED", timeout = 30,
                    controlId = CONTROL_ID) {
  needsStatusUrl(statusUrl);
  return client.calling.detect(callId, {
    control_id: controlId, detect: { type: "fax", params: { tone } },
    timeout, status_url: statusUrl,
  });
}

/** DTMF detection: report when any of these digits is pressed. */
export function digits(callId: string, statusUrl?: string, wanted = "0123456789",
                       timeout = 30, controlId = CONTROL_ID) {
  needsStatusUrl(statusUrl);
  return client.calling.detect(callId, {
    control_id: controlId, detect: { type: "digit", params: { digits: wanted } },
    timeout, status_url: statusUrl,
  });
}

/** Give up on the detection before its timeout. */
export function stop(callId: string, controlId = CONTROL_ID) {
  return client.calling.detectStop(callId, { control_id: controlId });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, statusUrl] = process.argv.slice(2);
  if (!callId) {
    console.log("usage: npm start <machine|fax|digits|stop> <call_id> [status_url]");
  } else if (cmd === "machine") {
    console.log(await machine(callId, statusUrl));
  } else if (cmd === "fax") {
    console.log(await fax(callId, statusUrl));
  } else if (cmd === "digits") {
    console.log(await digits(callId, statusUrl));
  } else if (cmd === "stop") {
    console.log(await stop(callId));
  }
}
