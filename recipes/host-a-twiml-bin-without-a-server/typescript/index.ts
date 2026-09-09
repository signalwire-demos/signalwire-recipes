/**
 * Host a TwiML bin without a server.
 *
 * A cXML document does not need a server of yours. One POST to
 * `/api/fabric/resources/cxml_scripts` with `display_name` and `contents`
 * stores it, and the response carries the `request_url` SignalWire serves it
 * from. One more POST puts a phone number on it. The compat twin is
 * `POST /Accounts/{AccountSid}/LamlBins` with `Name` and `Contents`.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.fabric, RestClient.phoneNumbers).
 *
 *     npm start create
 *     npm start point <script_id> +15551230000
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

export const NAME = "workshop line";
export const FORWARD_TO = process.env["FORWARD_TO"] ?? "+15550100001";

/** The whole application: a greeting and a forward, as TwiML. */
export const contents = (forwardTo = FORWARD_TO) =>
  '<?xml version="1.0" encoding="UTF-8"?>\n'
  + "<Response>\n"
  + "  <Say>Connecting you to the workshop.</Say>\n"
  + `  <Dial timeout="20">${forwardTo}</Dial>\n`
  + "</Response>\n";

/** One POST. The response carries the id and the URL SignalWire serves it from. */
export async function create(): Promise<[string, string]> {
  const made = await client.fabric.cxmlScripts.create({ display_name: NAME,
                                                        contents: contents() });
  return [made["id"], made["cxml_script"]["request_url"]];
}

/** `filter_number` is a contains match, so compare the number exactly. */
export async function numberId(e164: string): Promise<string> {
  const page = await client.phoneNumbers.list({ filter_number: e164 });
  for (const item of (page["data"] ?? []) as { id: string; number: string }[]) {
    if (item.number === e164) return item.id;
  }
  throw new Error(`${e164} is not a number in this project`);
}

/** Route inbound calls on the number to the hosted script. */
export async function pointNumber(scriptId: string, e164: string) {
  return client.fabric.resources.assignPhoneRoute(scriptId, {
    phone_route_id: await numberId(e164), handler: "calling",
  });
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, id, number] = process.argv.slice(2);
  if (cmd === "create") {
    const [scriptId, url] = await create();
    console.log(scriptId, url);
  } else if (cmd === "point" && id && number) {
    console.log(await pointNumber(id, number));
  } else {
    console.log("usage: npm start create | npm start point <script_id> <e164>");
  }
}
