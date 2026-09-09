/**
 * Create a hosted voice AI agent with one REST call.
 *
 * The agent you would serve from your own host is the agent SignalWire can
 * host for you. `AgentBase` renders the `ai` verb; its `prompt`, `params` and
 * `post_prompt` are exactly the fields `POST /api/fabric/resources/ai_agents`
 * takes, and the spec points at the SWML `ai` reference for each. One more
 * POST puts a phone number on the resource. No server of yours stays running.
 *
 * Written against @signalwire/sdk 2.0.5 (AgentBase, RestClient.fabric).
 *
 *     npm start create
 *     npm start point <agent_id> +15551230000
 */
import "dotenv/config";
import { AgentBase, RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

export const NAME = "ridgeline-front-desk";

/** The same definition you would run yourself, rendered rather than served. */
export class FrontDesk extends AgentBase {
  constructor() {
    super({ name: NAME, route: "/front-desk" });
    this.promptAddSection("Role", { body: "You answer the phone for Ridgeline Cycles, "
                                          + "a bike shop. Be brief and warm." });
    this.promptAddSection("Hours", { body: "Open Monday to Friday, nine to five, "
                                           + "Eastern time. Closed weekends." });
    this.promptAddSection("Limits", {
      body: "You cannot book repairs. Offer the shop number for that "
          + "and end the call kindly.",
    });
    this.setPostPrompt("Summarise the call in one sentence.");
    this.setParams({ end_of_speech_timeout: 700 });
  }
}

type Step = Record<string, Record<string, unknown>>;

/** The `ai` verb the agent renders, which is what the hosted resource needs. */
export async function definition(agent: AgentBase = new FrontDesk()) {
  const doc = JSON.parse(await agent.renderSwml()) as { sections: { main: Step[] } };
  const ai = doc.sections.main.find((step) => "ai" in step)!["ai"];
  const body: Record<string, unknown> = { name: NAME, prompt: ai["prompt"] };
  for (const key of ["params", "post_prompt"]) {
    if (key in ai) body[key] = ai[key];
  }
  return body;
}

/** One POST. The response carries the resource id a number can point at. */
export async function create() {
  return client.fabric.aiAgents.create(await definition());
}

/** `filter_number` is a contains match, so compare the number exactly. */
export async function numberId(e164: string): Promise<string> {
  const page = await client.phoneNumbers.list({ filter_number: e164 });
  for (const item of (page["data"] ?? []) as { id: string; number: string }[]) {
    if (item.number === e164) return item.id;
  }
  throw new Error(`${e164} is not a number in this project`);
}

/** Route inbound calls on the number to the hosted agent. */
export async function pointNumber(resourceId: string, e164: string) {
  return client.fabric.resources.assignPhoneRoute(resourceId, {
    phone_route_id: await numberId(e164), handler: "calling",
  });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, id, number] = process.argv.slice(2);
  if (cmd === "create") {
    const made = await create();
    console.log(made["id"], made["display_name"]);
  } else if (cmd === "point" && id && number) {
    console.log(await pointNumber(id, number));
  } else {
    console.log("usage: npm start create | npm start point <agent_id> <e164>");
  }
}
