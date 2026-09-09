/**
 * Start from a prefab agent.
 *
 * The SDK ships complete agents as classes. You pass configuration, not a
 * prompt. The prefab writes its prompt sections and registers its tools with
 * their handlers. The receptionist also sets its voice and wires its transfer.
 *
 *   ReceptionistAgent  greets, records who is calling and why, transfers to a
 *                      department by name
 *   SurveyAgent        asks scripted questions in order, validates each answer
 *                      against its type, logs it
 *
 * PREFAB selects which one this process serves. Both are built here so the
 * verifier can prove both.
 *
 * Written against @signalwire/sdk 2.0.5.
 *
 *     npm start                       # the receptionist
 *     PREFAB=survey npm start         # the survey
 */
import "dotenv/config";
import { type AgentBase, ReceptionistAgent, SurveyAgent,
         type SurveyQuestion } from "@signalwire/sdk";

// Every department the receptionist may transfer to. `name` becomes an enum
// on the transfer tool's argument, and the handler refuses a name not here.
export const DEPARTMENTS = [
  { name: "sales", description: "Pricing, availability and new orders",
    number: process.env["SALES_NUMBER"] ?? "+15551230001" },
  { name: "workshop", description: "Repairs, servicing and appointments",
    number: process.env["WORKSHOP_NUMBER"] ?? "+15551230002" },
];

// Each question carries a type; the prefab validates answers against it.
export const QUESTIONS: SurveyQuestion[] = [
  { id: "on_time", type: "yes_no",
    text: "Was your bike ready when we said it would be?" },
  { id: "rating", type: "rating", scale: 5,
    text: "From one to five, how would you rate the work?" },
  { id: "notes", type: "open_ended", required: false,
    text: "Anything else you want the workshop to know?" },
];

type Json = Record<string, unknown>;
type Hook = Promise<Json> | undefined;

/**
 * The platform posts a tool's arguments as `argument: {parsed: [args], raw}`
 * (the documented SWAIG tool webhook). The 2.0.5 `/swaig` route hands
 * `argument` to the prefab's handlers as posted, so they would read `parsed`
 * and `raw` instead of the caller's name. This unwraps the documented shape
 * before dispatch and steps aside for anything else.
 */
function unwrapParsed(agent: AgentBase, name: string, args: Json,
                      raw: Json): Hook {
  const parsed = args["parsed"];
  if (!Array.isArray(parsed)) return undefined;
  const tool = agent.getTools().find((t) => t.name === name);
  return tool ? tool.execute((parsed[0] ?? {}) as Json, raw) : undefined;
}

export class Reception extends ReceptionistAgent {
  override onFunctionCall(name: string, args: Json, raw: Json): Hook {
    return unwrapParsed(this, name, args, raw);
  }
}

export class Survey extends SurveyAgent {
  override onFunctionCall(name: string, args: Json, raw: Json): Hook {
    return unwrapParsed(this, name, args, raw);
  }
}

export function buildReceptionist() {
  return new Reception({
    departments: DEPARTMENTS,
    greeting: "Ridgeline Cycles, how can I help?",
    name: "reception", route: "/reception",
  });
}

export function buildSurvey() {
  return new Survey({
    surveyName: "Workshop follow-up",
    brandName: "Ridgeline Cycles",
    questions: QUESTIONS,
    introduction: "This is a short follow-up on your recent repair.",
    conclusion: "Thanks. Your answers go straight to the workshop.",
    name: "survey", route: "/survey",
  });
}

export const BUILDERS = { receptionist: buildReceptionist, survey: buildSurvey };

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  for (const name of ["SWML_BASIC_AUTH_USER", "SWML_BASIC_AUTH_PASSWORD"]) {
    if (!process.env[name]) throw new Error(`${name} is required; see .env.example`);
  }
  const which = (process.env["PREFAB"] ?? "receptionist") as keyof typeof BUILDERS;
  BUILDERS[which]().serve({ port: Number(process.env["PORT"] ?? 3000) });
}
