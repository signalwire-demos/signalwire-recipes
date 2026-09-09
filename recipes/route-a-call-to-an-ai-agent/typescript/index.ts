/**
 * Route a phone number to an AI agent.
 *
 * Two requests. The first makes a SWML webhook resource that points at your
 * agent's URL; the second attaches a phone number you already own to it.
 *
 * The indirection is the point. The number is bound to a resource, not to a
 * URL, so moving the agent is one PATCH of the resource rather than a change
 * on every number pointing at it.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient.fabric).
 *
 *     npm start
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();

export const AGENT_URL = process.env["AGENT_URL"]
  ?? "https://your-host.example.com/agent";
export const PHONE_ROUTE_ID = process.env["PHONE_ROUTE_ID"]
  ?? "00000000-0000-0000-0000-000000000000";

/** Create the resource, then bind the number to it. */
export async function pointNumberAt(agentUrl = AGENT_URL, phoneRouteId = PHONE_ROUTE_ID) {
  const resource = await client.fabric.swmlWebhooks.create({
    name: "support agent",
    // where SignalWire fetches the document when a call arrives
    primary_request_url: agentUrl,
    primary_request_method: "POST",
    // a second URL for SignalWire to try if the primary request fails.
    // Host it apart from the agent, or it shares the outage it covers.
    fallback_request_url: process.env["FALLBACK_URL"] ?? `${agentUrl}/fallback`,
    fallback_request_method: "POST",
  });
  await client.fabric.resources.assignPhoneRoute(resource["id"], {
    phone_route_id: phoneRouteId,
    // this resource answers calls, not messages
    handler: "calling",
  });
  return resource;
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  console.log(await pointNumberAt());
}
