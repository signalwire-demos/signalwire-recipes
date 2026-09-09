/**
 * Control when a caller can interrupt a voice agent.
 *
 * Interruption and turn-taking are `ai.params`, not prompt sentences.
 * `enable_barge` says which speech events may cut the agent off,
 * `barge_min_words` how many words it takes, `static_greeting_no_barge`
 * protects the greeting, and `end_of_speech_timeout`, `first_word_timeout` and
 * `speech_event_timeout` decide when the caller has finished. The schema bounds
 * each one, and the verifier proves the rendered document carries exactly
 * these keys within those bounds.
 *
 * Written against @signalwire/sdk 2.0.5.
 *
 *     npm start            # serves /front-desk/
 */
import "dotenv/config";
import { AgentBase } from "@signalwire/sdk";

/**
 * `enable_barge` is a string or a boolean, and false is how you turn it off.
 * An environment variable is always a string, so "false" has to become the
 * boolean or the document carries a value the reference does not list.
 */
export function bargeValue(raw: string): string | boolean {
  const word = raw.trim().toLowerCase();
  if (word === "false") return false;
  if (word === "true") return true;
  return raw;
}

/** An integer setting. A typo in .env should stop the process, not ship. */
export function intValue(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw.trim() === "") return fallback;
  const value = Number(raw);
  if (!Number.isInteger(value)) throw new Error(`expected an integer, got ${raw}`);
  return value;
}

/** A number setting. Whole values stay integers so both surfaces agree. */
export function numberValue(raw: string | undefined, fallback: number): number {
  if (raw === undefined || raw.trim() === "") return fallback;
  const value = Number(raw);
  if (!Number.isFinite(value)) throw new Error(`expected a number, got ${raw}`);
  return value;
}

const envInt = (name: string, fallback: number) => intValue(process.env[name], fallback);
const envBool = (name: string, fallback: boolean) => {
  const raw = (process.env[name] ?? String(fallback)).trim().toLowerCase();
  return ["1", "true", "yes"].includes(raw);
};

// The line the platform speaks before the model does. It has to be a
// static_greeting, because static_greeting_no_barge is what protects it; a
// prompt telling the model to open with a line protects nothing.
export const GREETING = "Ridgeline Cycles, how can I help?";

// The turn-taking settings. Each is documented on ai.params; the schema holds
// the bounds the verifier checks, and the defaults where it states one.
export const TURN_TAKING: Record<string, string | number | boolean> = {
  // what static_greeting_no_barge below refers to
  static_greeting: GREETING,
  // which events interrupt the agent: "complete", "partial", "all", or a
  // boolean. The default is "complete,partial"; false turns barging off
  enable_barge: bargeValue(process.env["ENABLE_BARGE"] ?? "complete,partial"),
  // how many words the caller must say before it counts as an interruption, 1-99
  barge_min_words: envInt("BARGE_MIN_WORDS", 3),
  // while the caller talks over the agent, the agent does not answer them (default)
  transparent_barge: envBool("TRANSPARENT_BARGE", true),
  // a cough is not an interruption
  interrupt_on_noise: envBool("INTERRUPT_ON_NOISE", false),
  // the opening line plays through even if the caller starts talking
  static_greeting_no_barge: envBool("STATIC_GREETING_NO_BARGE", true),
  // ms of silence that ends the caller's turn, 250-10000, default 700
  end_of_speech_timeout: envInt("END_OF_SPEECH_TIMEOUT", 700),
  // ms to wait for a first word once speech is detected, 0-10000, default 1000
  first_word_timeout: envInt("FIRST_WORD_TIMEOUT", 1000),
  // ms to wait for a speech event, 0-10000, default 1400
  speech_event_timeout: envInt("SPEECH_EVENT_TIMEOUT", 1400),
  // how loud the caller must be to be heard, 0.0-100.0 dB, default 52
  energy_level: numberValue(process.env["ENERGY_LEVEL"], 52),
  // end the turn on sentence-ending punctuation in the partial transcript (default)
  enable_turn_detection: envBool("ENABLE_TURN_DETECTION", true),
};

export class FrontDesk extends AgentBase {
  constructor(turnTaking?: Record<string, unknown>) {
    super({ name: "front-desk", route: "/front-desk" });
    this.promptAddSection("Role", { body: "You answer the phone for Ridgeline Cycles, "
                                          + "a bike shop. Be brief and warm." });
    // the whole recipe: turn-taking is configuration, not prose
    this.setParams(turnTaking === undefined ? TURN_TAKING : turnTaking);
  }
}

/** The document the platform receives. */
export const render = (turnTaking?: Record<string, unknown>) =>
  JSON.parse(new FrontDesk(turnTaking).renderSwml()) as Record<string, unknown>;

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const name of ["SWML_BASIC_AUTH_USER", "SWML_BASIC_AUTH_PASSWORD"]) {
    if (!process.env[name]) throw new Error(`${name} is required; see .env.example`);
  }
  new FrontDesk().serve({ port: Number(process.env["PORT"] ?? 3000) });
}
