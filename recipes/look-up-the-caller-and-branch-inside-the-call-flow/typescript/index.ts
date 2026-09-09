/**
 * Look up the caller and branch inside the call flow.
 *
 * The call fetches the caller's record itself. `request` with `save_variables`
 * true parses your API's JSON into `request_response.<field>`; `switch` then
 * branches on one of those fields, and a `cond` around it sends the call to a
 * human when the lookup fails. The document is hosted as a Call Flow, so no
 * server of yours is in the call path.
 *
 * Written against @signalwire/sdk 2.0.5 (SWMLService, RestClient.fabric).
 *
 *     npm start deploy
 *     npm start point <resource_id> +15551230000
 */
import "dotenv/config";
import { RestClient, SWMLService } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

// your system of record: the endpoint the call asks about the caller
export const CRM_URL = process.env["CRM_URL"] ?? "https://crm.example.com/lookup";
const CRM_TOKEN = process.env["CRM_TOKEN"] ?? "replace-me";

// where each tier lands. An unknown tier is treated as standard.
export const DESKS: Record<string, string> = {
  gold: process.env["GOLD_NUMBER"] ?? "+15550100001",
  standard: process.env["STANDARD_NUMBER"] ?? "+15550100002",
};
export const APOLOGY = "One moment, I could not look up your account.";

// The spec pairs relayml with flow_data: provide both or omit both.
export const FLOW_DATA = {
  generated_by: "signalwire-recipes",
  recipe: "look-up-the-caller-and-branch-inside-the-call-flow",
};

type Json = Record<string, unknown>;

/** The routing document, each verb validated as it is added. */
export function build() {
  const service = new SWMLService({ name: "crm-router", route: "/router" });
  service.resetDocument();
  service.addVerb("answer", {});
  // %{call.from} is substituted at runtime; the schema accepts ${...} too
  service.addVerb("request", {
    url: CRM_URL,
    method: "POST",
    headers: { "Content-Type": "application/json",
               Authorization: `Bearer ${CRM_TOKEN}` },
    body: { phone: "%{call.from}" },
    // without this the response is not parsed into request_response.<field>
    save_variables: true,
    connect_timeout: 3,
    timeout: 5,
  });
  // cond takes an array; it is appended so both surfaces build it the same way
  const document = service.getDocument() as { sections: { main: Json[] } };
  const cases: Json = {};
  for (const [tier, number] of Object.entries(DESKS)) {
    cases[tier] = [{ connect: { to: number, timeout: 25 } }];
  }
  document.sections.main.push({ cond: [
    { when: "request_result == 'success'",
      then: [{ switch: {
        variable: "request_response.tier",
        case: cases,
        // a record with a tier you do not know is still a customer
        default: [{ connect: { to: DESKS["standard"], timeout: 25 } }],
      } }] },
    // the lookup failed or timed out: reach a human anyway
    { else: [{ play: { url: `say:${APOLOGY}` } },
             { connect: { to: DESKS["standard"], timeout: 25 } }] },
  ] });
  service.addVerb("hangup", {});
  return service;
}

/** Host the document as a Call Flow. Returns the resource. */
export async function deploy(title = "Ridgeline Cycles router") {
  return client.fabric.callFlows.create({
    title, relayml: build().getDocument(), flow_data: FLOW_DATA,
  });
}

/** `filter_number` is a contains match, so compare the number exactly. */
export async function numberId(e164: string): Promise<string> {
  const page = await client.phoneNumbers.list({ filter_number: e164 });
  for (const item of (page["data"] ?? []) as { id: string; number: string }[]) {
    if (item.number === e164) return item.id;
  }
  throw new Error(`${e164} is not a number on this project`);
}

/** Route inbound calls on the number to the hosted flow. */
export async function pointNumber(resourceId: string, e164: string) {
  return client.fabric.resources.assignPhoneRoute(resourceId, {
    phone_route_id: await numberId(e164), handler: "calling",
  });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, id, number] = process.argv.slice(2);
  if (cmd === "deploy") {
    console.log((await deploy())["id"]);
  } else if (cmd === "point" && id && number) {
    console.log(await pointNumber(id, number));
  } else {
    console.log("usage: npm start deploy | npm start point <resource_id> <e164>");
  }
}
