/**
 * Pause and resume a call recording over REST.
 *
 * Four call commands share one `controlId`: `calling.record` starts a recording
 * on a live call, `calling.record.pause` and `calling.record.resume` bracket the
 * part you must not keep, and `calling.record.stop` ends it.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start start <call_id> [status_url]
 *     npm start pause <call_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// one id names the recording across start, pause, resume and stop
export const CONTROL_ID = "agent-desk-recording";

// how the pause reads in the file: `skip` cuts it out, `silence` keeps the timing
export const PAUSE_BEHAVIOR = "silence";

// The REST defaults are prompt-style: stop after 4s without speech, after 0.5s
// of silence, or on `#`. SWML's whole-call verb, record_call, defaults these
// three to 0, 0 and "", and a call recording wants those.
export const WHOLE_CALL = { initial_timeout: 0, end_silence_timeout: 0, terminators: "" };

/** Record both directions to one stereo mp3, for as long as the call runs. */
export function start(callId: string, statusUrl?: string, controlId = CONTROL_ID) {
  const audio = {
    stereo: true, direction: "both", format: "mp3", max_length: 0, ...WHOLE_CALL,
  };
  const params: Record<string, unknown> = { control_id: controlId, record: { audio } };
  if (statusUrl) {
    // the recording URL arrives here when the recording finishes
    params["status_url"] = statusUrl;
  }
  return client.calling.record(callId, params);
}

/** Stop capturing. The file keeps the gap as silence, or drops it with `skip`. */
export function pause(callId: string, controlId = CONTROL_ID, behavior = PAUSE_BEHAVIOR) {
  return client.calling.recordPause(callId, { control_id: controlId, behavior });
}

/** Capture again, into the same file. */
export function resume(callId: string, controlId = CONTROL_ID) {
  return client.calling.recordResume(callId, { control_id: controlId });
}

/** Finish the recording. The status_url from `start` gets the final URL. */
export function stop(callId: string, controlId = CONTROL_ID) {
  return client.calling.recordStop(callId, { control_id: controlId });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, ...rest] = process.argv.slice(2);
  const actions: Record<string, (id: string, ...a: string[]) => Promise<unknown>> = {
    start, pause, resume, stop,
  };
  if (!callId || !actions[cmd]) {
    console.log("usage: npm start <start|pause|resume|stop> <call_id> [status_url]");
  } else {
    console.log(await actions[cmd](callId, ...rest));
  }
}
