/**
 * Normalize spoken dates and phone numbers in a tool handler.
 *
 * Speech recognition hands the model "next Tuesday" and "four one five, five
 * five five, oh one two three". The tool takes those words as they are; the
 * handler turns them into an ISO date and an E.164 number, writes the machine
 * values to `global_data`, and reads both back in words the caller can check.
 * When it cannot, it says so with a typed state and asks for the piece it
 * needs. The prompt never asks the model to convert anything.
 *
 * Written against @signalwire/sdk 2.0.5.
 *
 *     npm start            # serves /callback/ and /callback/swaig
 */
import "dotenv/config";
import { AgentBase, FunctionResult } from "@signalwire/sdk";

type Json = Record<string, unknown>;
type Hook = Promise<Json> | undefined;

const MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
                     "august", "september", "october", "november", "december"];
const MONTHS: Record<string, number> = { sept: 9 };
MONTH_NAMES.forEach((m, i) => { MONTHS[m] = i + 1; MONTHS[m.slice(0, 3)] = i + 1; });
const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
                  "sunday"];
const UNITS: Record<string, number> = {
  first: 1, second: 2, third: 3, fourth: 4, fifth: 5, sixth: 6, seventh: 7, eighth: 8,
  ninth: 9, tenth: 10, eleventh: 11, twelfth: 12, thirteenth: 13, fourteenth: 14,
  fifteenth: 15, sixteenth: 16, seventeenth: 17, eighteenth: 18, nineteenth: 19,
  twentieth: 20, thirtieth: 30,
};
const TENS: Record<string, number> = { twenty: 20, thirty: 30 };
const DIGITS: Record<string, string> = {
  zero: "0", oh: "0", o: "0", one: "1", two: "2", three: "3", four: "4", five: "5",
  six: "6", seven: "7", eight: "8", nine: "9",
};
const DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven",
                     "eight", "nine"];
const FILLER = new Set(["on", "the", "of", "this", "at"]);
const DAY = 86_400_000;

/** The clock, as a UTC date at midnight. TODAY pins it for the verifier. */
export function today(): Date {
  const pinned = process.env["TODAY"];
  if (pinned) return new Date(`${pinned}T00:00:00Z`);
  const now = new Date();
  return new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
}

const words = (text: string | undefined) =>
  (text ?? "").toLowerCase().replace(/-/g, " ").replace(/[^a-z0-9/]+/g, " ").trim()
    .split(" ").filter(Boolean);

/** Monday is 0, as in Python. */
const weekday = (d: Date) => (d.getUTCDay() + 6) % 7;
const addDays = (d: Date, n: number) => new Date(d.getTime() + n * DAY);

function nextWeekday(start: Date, name: string) {
  const delta = ((WEEKDAYS.indexOf(name) - weekday(start)) % 7 + 7) % 7 || 7;
  return addDays(start, delta);
}

/** A calendar date, or undefined when the day does not exist in that month. */
function resolve(month: number, day: number, year: number | undefined, start: Date) {
  const make = (y: number) => {
    const d = new Date(Date.UTC(y, month - 1, day));
    return d.getUTCMonth() === month - 1 && d.getUTCDate() === day ? d : undefined;
  };
  if (year) return make(year);
  const thisYear = make(start.getUTCFullYear());
  if (!thisYear) return undefined;
  return thisYear >= start ? thisYear : make(start.getUTCFullYear() + 1);
}

/**
 * 'tomorrow', 'next Tuesday', 'the fifth of March', 'March 5th', '9/30'. A
 * weekday means the next one after today; 'next' adds a week. A month and day
 * with no year mean the next time that date comes round.
 */
export function normalizeDate(text: string | undefined, start: Date): Date | undefined {
  const all = words(text);
  const joined = all.join(" ");
  if (joined === "today") return start;
  if (joined === "tomorrow") return addDays(start, 1);
  if (joined === "day after tomorrow" || joined === "the day after tomorrow") {
    return addDays(start, 2);
  }
  const core = all.filter((w) => !FILLER.has(w));
  if (core.length === 1 && WEEKDAYS.includes(core[0]!)) {
    return nextWeekday(start, core[0]!);
  }
  if (core.length === 2 && core[0] === "next" && WEEKDAYS.includes(core[1]!)) {
    return addDays(nextWeekday(start, core[1]!), 7);
  }
  if (core.length === 1) {
    const m = /^(\d{1,2})\/(\d{1,2})(?:\/(\d{4}))?$/.exec(core[0]!);
    if (m) {
      return resolve(Number(m[1]), Number(m[2]), m[3] ? Number(m[3]) : undefined, start);
    }
  }
  let month: number | undefined, day: number | undefined, year: number | undefined;
  for (let i = 0; i < core.length; i++) {
    const w = core[i]!;
    const next = core[i + 1];
    if (w in MONTHS && month === undefined) month = MONTHS[w];
    else if (w in TENS && next !== undefined && (UNITS[next] ?? 10) < 10) {
      day = TENS[w]! + UNITS[next]!;
      i++;
    } else if (w in UNITS) day = UNITS[w];
    else if (/^\d{1,2}(st|nd|rd|th)?$/.test(w)) day = Number(w.replace(/\D/g, ""));
    else if (/^\d{4}$/.test(w)) year = Number(w);
    else return undefined;
  }
  if (month === undefined || day === undefined) return undefined;
  return resolve(month, day, year, start);
}

/** Spoken or written digits to E.164, North America assumed. */
export function normalizePhone(text: string | undefined): string | undefined {
  const digits = words(text).filter((w) => w in DIGITS || /^\d+$/.test(w))
    .map((w) => DIGITS[w] ?? w).join("");
  if (digits.length === 10) return "+1" + digits;
  if (digits.length === 11 && digits.startsWith("1")) return "+" + digits;
  return undefined;
}

function ordinal(n: number) {
  const tail = n % 100;
  if (tail >= 11 && tail <= 13) return `${n}th`;
  const small: Record<number, string> = { 1: "st", 2: "nd", 3: "rd" };
  const suffix = small[n % 10] ?? "th";
  return `${n}${suffix}`;
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** 'Tuesday, September 8th': the weekday lets the caller catch a wrong date. */
export function spokenDate(d: Date) {
  const day = cap(WEEKDAYS[weekday(d)]!);
  const month = cap(MONTH_NAMES[d.getUTCMonth()]!);
  return `${day}, ${month} ${ordinal(d.getUTCDate())}`;
}

/** 'four one five, five five five, zero one two three', grouped for reading back. */
export function spokenPhone(e164: string) {
  const n = e164.slice(2);
  return [n.slice(0, 3), n.slice(3, 6), n.slice(6)]
    .map((g) => [...g].map((c) => DIGIT_WORDS[Number(c)]).join(" ")).join(", ");
}

const iso = (d: Date) => d.toISOString().slice(0, 10);

export class CallbackDesk extends AgentBase {
  constructor() {
    super({ name: "callback-desk", route: "/callback" });
    this.promptAddSection("Role", {
      body: "You schedule callbacks for a repair shop. Pass the day and the number "
          + "exactly as the caller says them; the tool converts them. Read back what "
          + "the tool returns and ask the caller to confirm.",
    });
    this.defineTool({
      name: "schedule_callback",
      description: "Schedule a callback on a day at a phone number. Pass both as the "
                 + "caller said them. Do not convert or reformat either one.",
      parameters: {
        type: "object",
        properties: {
          date: { type: "string",
                  description: "The day in the caller's words: 'tomorrow', "
                             + "'next Tuesday', 'the fifth of March', 'March 5th', "
                             + "'9/30'." },
          phone: { type: "string",
                   description: "The number as spoken or read: 'four one five, five five "
                              + "five, oh one two three' or '(415) 555-0123'." },
        },
        required: ["date", "phone"],
      },
      handler: (args) => {
        const dateText = args["date"] as string | undefined;
        const phoneText = args["phone"] as string | undefined;
        const when = normalizeDate(dateText, today());
        if (!when) {
          return new FunctionResult(
            `UNPARSED_DATE: could not read '${dateText}' as a date. `
            + "Ask the caller for the day and the month, then call again.");
        }
        const number = normalizePhone(phoneText);
        if (!number) {
          return new FunctionResult(
            `UNPARSED_PHONE: '${phoneText}' was not a ten `
            + "digit number. Ask the caller to say it digit by digit, then call again.");
        }
        // the machine values go to global_data; the caller hears words
        return new FunctionResult(`Callback set for ${spokenDate(when)} at `
            + `${spokenPhone(number)}. Read both back and ask the caller to confirm.`)
          .updateGlobalData({ callback: { date: iso(when), phone: number } });
      },
    });
  }

  /**
   * The platform posts a tool's arguments as `argument: {parsed: [args], raw}`.
   * The 2.0.5 `/swaig` route hands `argument` to the handler as posted, so
   * this hook unwraps the documented shape before dispatch.
   */
  override onFunctionCall(name: string, args: Json, raw: Json): Hook {
    const parsed = args["parsed"];
    if (!Array.isArray(parsed)) return undefined;
    const tool = this.getTools().find((t) => t.name === name);
    return tool ? tool.execute((parsed[0] ?? {}) as Json, raw) : undefined;
  }
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const name of ["SWML_BASIC_AUTH_USER", "SWML_BASIC_AUTH_PASSWORD"]) {
    if (!process.env[name]) throw new Error(`${name} is required; see .env.example`);
  }
  new CallbackDesk().serve({ port: Number(process.env["PORT"] ?? 3000) });
}
