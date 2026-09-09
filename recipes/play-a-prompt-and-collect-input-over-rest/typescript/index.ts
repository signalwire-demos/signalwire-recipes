/**
 * Play a prompt and collect digits or speech over REST.
 *
 * `calling.play` speaks text or plays a file into a live call,
 * `calling.play.stop` cuts it short, and `calling.collect` gathers keypad digits
 * or speech. Results do not come back in the HTTP response: the platform posts
 * them to the `status_url` you give, so a collect without one is refused here
 * before it is sent.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start say <call_id> "Please key in your account number"
 *     npm start digits <call_id> https://your-host/collect-events
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// one id per operation type; stop and collect.stop name them
export const PLAY_ID = "agent-desk-prompt";
export const COLLECT_ID = "agent-desk-input";

/** Speak `text` to the caller. Playback events go to statusUrl if given. */
export function say(callId: string, text: string, controlId = PLAY_ID,
                    statusUrl?: string) {
  const item = { type: "tts", params: { text } };
  const params: Record<string, unknown> = { control_id: controlId, play: [item] };
  if (statusUrl) {
    params["status_url"] = statusUrl;
  }
  return client.calling.play(callId, params);
}

/** Play an audio file from an HTTP(S) URL instead of speaking text. */
export function playFile(callId: string, url: string, controlId = PLAY_ID) {
  const item = { type: "audio", params: { url } };
  return client.calling.play(callId, { control_id: controlId, play: [item] });
}

/** Adjust a playing prompt, in dB. The spec's range is -40 to 40. */
export function setVolume(callId: string, volume: number, controlId = PLAY_ID) {
  if (!Number.isFinite(volume)) {
    // Number("loud") is NaN, and NaN fails every range comparison silently
    throw new Error(`volume must be a number of dB, not ${volume}`);
  }
  if (volume < -40 || volume > 40) {
    throw new Error(`volume must be between -40 and 40 dB, not ${volume}`);
  }
  return client.calling.playVolume(callId, { control_id: controlId, volume });
}

/** Cut the prompt short, for example when the caller starts keying digits. */
export function stopPlayback(callId: string, controlId = PLAY_ID) {
  return client.calling.playStop(callId, { control_id: controlId });
}

function needsStatusUrl(statusUrl: string | undefined): asserts statusUrl is string {
  // the result arrives only by webhook; without one the collect is unobservable
  if (!statusUrl) {
    throw new Error("a collect needs a status_url to deliver its result");
  }
}

/** Collect up to maxDigits keypad digits, ended early by #. */
export function askDigits(callId: string, statusUrl?: string, maxDigits = 10,
                          controlId = COLLECT_ID) {
  needsStatusUrl(statusUrl);
  const digits = { max: maxDigits, terminators: "#", digit_timeout: 5 };
  // start_input_timers defaults to false, and then initial_timeout never runs
  return client.calling.collect(callId, {
    control_id: controlId, digits, initial_timeout: 10,
    start_input_timers: true, status_url: statusUrl,
  });
}

/** Collect one spoken answer, ended by 1.5 seconds of silence. */
export function askSpeech(callId: string, statusUrl?: string, language = "en-US",
                          controlId = COLLECT_ID) {
  needsStatusUrl(statusUrl);
  const speech = { end_silence_timeout: 1.5, speech_timeout: 15, language };
  return client.calling.collect(callId, {
    control_id: controlId, speech, initial_timeout: 10,
    start_input_timers: true, status_url: statusUrl,
  });
}

/** Give up waiting for input. */
export function stopCollect(callId: string, controlId = COLLECT_ID) {
  return client.calling.collectStop(callId, { control_id: controlId });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, arg] = process.argv.slice(2);
  if (!callId) {
    console.log("usage: npm start <say|file|stop|digits|speech|cancel> <call_id> [arg]");
  } else if (cmd === "say") {
    console.log(await say(callId, arg));
  } else if (cmd === "file") {
    console.log(await playFile(callId, arg));
  } else if (cmd === "stop") {
    console.log(await stopPlayback(callId));
  } else if (cmd === "volume") {
    console.log(await setVolume(callId, Number(arg)));
  } else if (cmd === "digits") {
    console.log(await askDigits(callId, arg));
  } else if (cmd === "speech") {
    console.log(await askSpeech(callId, arg));
  } else if (cmd === "cancel") {
    console.log(await stopCollect(callId));
  }
}
