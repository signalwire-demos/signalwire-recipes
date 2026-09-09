/**
 * Start, steer and stop live translation on a call in progress.
 *
 * `calling.live_translate` carries one `action`, and the spec documents four:
 * `start`, `inject`, `summarize` and `stop`. Together they turn translation
 * into something your backend switches on partway through a call, speaks into,
 * and asks for a summary of, rather than something the document decided up
 * front.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.calling).
 *
 *     npm start start <call_id> en-US es-ES
 *     npm start stop <call_id>
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// the spec's two directions, which are also the two sides of the call
export const DIRECTIONS = ["remote-caller", "local-caller"] as const;
export type Direction = (typeof DIRECTIONS)[number];

/** Translate both sides, each hearing the other's language. */
export function start(callId: string, fromLang = "en-US", toLang = "es-ES",
                      webhook?: string) {
  const inner: Record<string, unknown> = {
    from_lang: fromLang, to_lang: toLang, direction: [...DIRECTIONS],
    speech_engine: "deepgram", live_events: true,
  };
  if (webhook) {
    // translation events land here while the call runs
    inner["webhook"] = webhook;
  }
  return client.calling.liveTranslate(callId, { action: { start: inner } });
}

/** Speak a line into the conversation, translated on the way. */
export function say(callId: string, message: string,
                    direction: Direction = "remote-caller") {
  if (!DIRECTIONS.includes(direction)) {
    throw new Error(
      `direction must be one of ${DIRECTIONS.join(", ")}, not '${direction}'`);
  }
  return client.calling.liveTranslate(callId, {
    action: { inject: { message, direction } },
  });
}

/** Ask for a summary of the translated conversation so far. */
export function summary(callId: string, webhook: string, prompt?: string) {
  const inner: Record<string, unknown> = { webhook };
  if (prompt) {
    inner["prompt"] = prompt;
  }
  return client.calling.liveTranslate(callId, { action: { summarize: inner } });
}

/** End translation. The call carries on untranslated. */
export function stop(callId: string) {
  return client.calling.liveTranslate(callId, { action: { stop: {} } });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, callId, a, b] = process.argv.slice(2);
  if (!callId) {
    console.log("usage: npm start <start|say|summary|stop> <call_id> [args]");
  } else if (cmd === "start") {
    console.log(await start(callId, a, b));
  } else if (cmd === "say") {
    console.log(await say(callId, a));
  } else if (cmd === "summary") {
    console.log(await summary(callId, a));
  } else if (cmd === "stop") {
    console.log(await stop(callId));
  }
}
