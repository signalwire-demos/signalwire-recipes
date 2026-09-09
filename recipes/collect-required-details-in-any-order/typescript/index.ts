/**
 * Collect required details in any order.
 *
 * A caller reporting an absence gives the details in whatever order they come
 * to mind. One tool, `record_detail`, takes a field name and a value and
 * writes it into `global_data`; the handler answers with what is still
 * missing. A second tool, `submit_report`, reads the collected details from
 * the request body and refuses until every required field is present. The
 * prompt asks; the handlers keep the checklist.
 *
 * Written against @signalwire/sdk 2.0.5.
 *
 *     npm start            # serves /absence/ and /absence/swaig
 */
import "dotenv/config";
import { AgentBase, FunctionResult } from "@signalwire/sdk";

type Json = Record<string, unknown>;
type Hook = Promise<Json> | undefined;

// The checklist. Order here is the order the model is offered, nothing more:
// the caller may fill it in any order.
export const REQUIRED: Record<string, string> = {
  employee_name: "the employee's name",
  shift_date: "the date of the shift",
  reason: "the reason for the absence",
};
export const OPTIONAL: Record<string, string> = {
  expected_return: "when they expect to be back",
  notes: "anything else for the manager",
};
export const FIELDS = { ...REQUIRED, ...OPTIONAL };

// Your HR system. A real one is an API call.
export const REPORTS: Json[] = [];

const text = (v: unknown) => String(v ?? "").trim();

/** The required fields not yet recorded, in checklist order. */
export const missing = (details: Record<string, string>) =>
  Object.keys(REQUIRED).filter((f) => !text(details[f]));

function statusLine(details: Record<string, string>) {
  const gaps = missing(details);
  if (gaps.length) {
    return "Still needed: " + gaps.map((f) => REQUIRED[f]).join(", ") + ".";
  }
  return "Everything required is recorded. Read the details back to the caller, "
       + "then call submit_report.";
}

const detailsOf = (raw: Json) =>
  ({ ...(((raw["global_data"] as Json | undefined) ?? {})["details"] as
      Record<string, string> | undefined ?? {}) });

export class AbsenceLine extends AgentBase {
  constructor() {
    super({ name: "absence-line", route: "/absence" });
    this.promptAddSection("Role", {
      body: "You take absence reports for a warehouse. Callers give details in any "
          + "order; record each one as soon as you hear it. Never ask for something "
          + "already recorded. When the tool says everything required is in, read "
          + "the details back and submit.",
    });
    this.defineTool({
      name: "record_detail",
      description: "Record one detail of the absence report as soon as the caller "
                 + "says it, in any order. Call it once per detail.",
      parameters: {
        type: "object",
        properties: {
          field: { type: "string", enum: Object.keys(FIELDS),
                   description: "Which detail this is." },
          value: { type: "string", description: "The detail in the caller's words." },
        },
        required: ["field", "value"],
      },
      handler: (args, raw) => {
        const field = text(args["field"]);
        const value = text(args["value"]);
        if (!Object.hasOwn(FIELDS, field)) {
          // the enum shapes what the model is offered; the handler decides
          return new FunctionResult(`UNKNOWN_FIELD: '${field}' is not on the report. `
            + `Record one of: ${Object.keys(FIELDS).join(", ")}.`);
        }
        if (!value) {
          return new FunctionResult(`EMPTY: nothing to record for ${FIELDS[field]}. `
                                    + "Ask the caller again.");
        }
        const details = detailsOf(raw);
        details[field] = value;
        // set_global_data merges top-level keys, so the whole details object
        // goes back, not one field of it
        return new FunctionResult(`Recorded ${FIELDS[field]}. ${statusLine(details)}`)
          .updateGlobalData({ details });
      },
    });
    this.defineTool({
      name: "submit_report",
      description: "File the absence report. Only call this after the tool has said "
                 + "everything required is recorded.",
      parameters: { type: "object", properties: {} },
      handler: (_args, raw) => {
        const filed = ((raw["global_data"] as Json | undefined) ?? {})["report_id"];
        if (filed) {
          // a retry, or the model asking twice: one report per call
          return new FunctionResult(
            `ALREADY_FILED: ${filed}. Tell the caller the reference.`);
        }
        const details = detailsOf(raw);
        const gaps = missing(details);
        if (gaps.length) {
          // the model asked to submit early; the checklist says no
          return new FunctionResult("MISSING: " + gaps.map((f) => REQUIRED[f]).join(", ")
                                    + ". Ask for those before submitting.");
        }
        const reportId = `ABS-${REPORTS.length + 1001}`;
        REPORTS.push({ id: reportId, ...details, filed_at: new Date().toISOString() });
        return new FunctionResult(
          `Report ${reportId} filed for ${details["employee_name"]}, `
          + `shift ${details["shift_date"]}. Tell the caller the reference and end `
          + "the call.")
          .updateGlobalData({ report_id: reportId });
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
  new AbsenceLine().serve({ port: Number(process.env["PORT"] ?? 3000) });
}
