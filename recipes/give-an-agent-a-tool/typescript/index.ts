/**
 * Give an agent a tool.
 *
 * A SWAIG function is not a separate concept from an LLM tool. It is rendered
 * into the same OpenAI-format tool schema the model sees every turn, so `name`,
 * `description` and the per-parameter descriptions are what decide whether the
 * model calls it and how it fills the arguments.
 *
 * The handler returns a FunctionResult, never a raw string, and returns a typed
 * state when the lookup fails so the model is told what to do instead of
 * guessing.
 *
 * Written against @signalwire/sdk 2.0.5.
 *
 *     npm start            # serves /orders/ and /orders/swaig
 */
import "dotenv/config";
import { AgentBase, FunctionResult } from "@signalwire/sdk";

// Your system of record. A real one is a database call.
export const ORDERS: Record<string, { status: string; eta: string; carrier: string }> = {
  "48815": { status: "out for delivery", eta: "today before 8pm", carrier: "Britewave" },
  "48816": { status: "packed", eta: "ships tomorrow", carrier: "Britewave" },
};

type Json = Record<string, unknown>;
type Hook = Promise<Json> | undefined;

export class OrderAgent extends AgentBase {
  constructor() {
    super({ name: "orders", route: "/orders" });
    this.promptAddSection("Role", {
      body: "You answer questions about orders for a home goods retailer. "
          + "Look the order up before you say anything about its status. "
          + "If the tool says the order was not found, ask the caller to "
          + "read the number back to you.",
    });
    // `parameters` is a JSON Schema object, the same shape the model sees.
    this.defineTool({
      name: "get_order_status",
      description: "Look up the delivery status of a customer's order by its order "
                 + "number. Use this BEFORE stating any status, date or carrier. "
                 + "Do not use it for returns or refunds.",
      parameters: {
        type: "object",
        properties: {
          order_id: {
            type: "string",
            description: "The order number, exactly five digits, no letters or "
                       + "dashes. Ask the caller to read it out if they have not "
                       + "given it.",
          },
        },
        required: ["order_id"],
      },
      // the caller hears one of these while the lookup runs
      fillers: { "en-US": ["Let me pull that order up.", "Checking on that order now."] },
      handler: (args) => {
        const orderId = String(args["order_id"] ?? "").trim();
        const order = ORDERS[orderId];
        if (!order) {
          // A typed failure. The model is told what to do next, so it does
          // not invent a delivery date to fill the silence.
          return new FunctionResult(
            `NOT_FOUND: no order ${orderId}. Ask the caller to read the `
            + "five digit order number back, then try again.");
        }
        // Format for speech here, not in the prompt.
        return new FunctionResult(
          `Order ${orderId} is ${order.status}, arriving ${order.eta} `
          + `with ${order.carrier}.`);
      },
    });
  }

  /**
   * The platform posts a tool's arguments as `argument: {parsed: [args], raw}`
   * (the documented SWAIG tool webhook). The 2.0.5 `/swaig` route hands
   * `argument` to the handler as posted, so a handler reading
   * `args["order_id"]` would find `parsed` and `raw` instead. This hook
   * unwraps the documented shape before dispatch and steps aside otherwise.
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
  new OrderAgent().serve({ port: Number(process.env["PORT"] ?? 3000) });
}
