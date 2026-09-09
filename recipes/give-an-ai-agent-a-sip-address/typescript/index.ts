/**
 * Give an AI agent a SIP address.
 *
 * A hosted resource can be reached over SIP as well as from a phone number.
 * `POST /api/fabric/sip_addresses` requires a URL-safe `name` and the
 * `calling_handler_resource_id` of the resource to ring, and the response
 * carries the `uri` a SIP phone or PBX dials. The `user` part defaults to `*`,
 * which accepts any username.
 *
 * 2.0.5 has no wrapper for this path, so the request goes through the HTTP
 * client every namespace shares.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient).
 *
 *     npm start <agent_resource_id> front-desk
 */
import "dotenv/config";
import { RestClient } from "@signalwire/sdk";

// reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE
export const client = new RestClient();
const http = (client.calling as unknown as {
  _http: { post(path: string, body: unknown): Promise<Record<string, string>> };
})._http;

// the spec: lowercase letters, numbers and hyphens, nothing else
const NAME_SHAPE = /^[a-z0-9-]+$/;

export type Created = { uri: string; user: string; name: string; resource_id: string };

/** Create a SIP address that rings the resource. Returns the platform's record. */
export async function giveAddress(resourceId: string, name: string, user?: string,
                                  encryption = "required"): Promise<Created> {
  if (!NAME_SHAPE.test(name)) {
    throw new Error(`name must be lowercase letters, numbers and hyphens: '${name}'`);
  }
  const body: Record<string, string> = {
    name, calling_handler_resource_id: resourceId, encryption,
  };
  if (user) {
    // otherwise the spec's default `*` accepts any username
    body["user"] = user;
  }
  return http.post("/api/fabric/sip_addresses", body) as Promise<Created>;
}

/** What to type into the SIP phone. */
export const dialString = (created: Created) => created.uri;

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [resourceId, name, user] = process.argv.slice(2);
  if (!resourceId || !name) {
    console.log("usage: npm start <agent_resource_id> <name> [user]");
  } else {
    console.log(dialString(await giveAddress(resourceId, name, user)));
  }
}
