/**
 * Let your users buy a phone number through your app.
 *
 * Onboarding uses your credentials: `POST /api/projects` creates the tenant's
 * subproject and `POST /api/project/tokens` issues a token bound to it. Every
 * number request after that goes through a second RestClient built from the
 * tenant's own credentials, so your platform token is never used on their
 * behalf.
 *
 * Written against @signalwire/sdk 2.0.5 (RestClient, RestClient.phoneNumbers).
 *
 *     npm start onboard "Acme Dental"
 *     npm start buy "Acme Dental" +14155550123 https://your-host/acme/
 */
import "dotenv/config";
import { readFileSync, writeFileSync, renameSync, existsSync } from "node:fs";
import { RestClient } from "@signalwire/sdk";

// your own credentials, used for onboarding and nothing else
export const platform = new RestClient();
const SPACE = process.env["SIGNALWIRE_SPACE"] ?? "";

// stands in for the table where you keep each tenant's credentials
export const TENANTS_PATH = process.env["TENANTS_PATH"] ?? "tenants.json";

// what a tenant's token may do. management is deliberately absent, so the token
// cannot create further projects or tokens
export const PERMISSIONS = ["numbers", "calling", "messaging"];

export type Tenant = {
  name: string; project_id: string; token_id: string;
  permissions: string[]; token: string;
};

function load(): Record<string, Tenant> {
  if (!existsSync(TENANTS_PATH)) return {};
  return JSON.parse(readFileSync(TENANTS_PATH, "utf-8"));
}

function save(tenants: Record<string, Tenant>) {
  const tmp = `${TENANTS_PATH}.tmp`;
  writeFileSync(tmp, JSON.stringify(tenants, null, 2), "utf-8");
  renameSync(tmp, TENANTS_PATH);
}

/** Create the tenant's subproject and a token bound to it. Stores both. */
export async function onboard(name: string, permissions = PERMISSIONS): Promise<Tenant> {
  // 2.0.5 wraps the tokens path (client.project.tokens) but not POST
  // /api/projects, so the subproject goes through the HTTP client every
  // namespace shares
  const http = (platform.calling as unknown as {
    _http: { post(path: string, body: unknown): Promise<Record<string, string>> };
  })._http;
  const project = await http.post("/api/projects",
                                  { name, force_https_requests: true });
  const token = await platform.project.tokens.create({
    name: `${name} numbers`, permissions: [...permissions], subproject_id: project["id"],
  });
  // token_id is the only handle for PATCH or DELETE later: the spec documents
  // no way to list a project's tokens
  const record: Tenant = {
    name, project_id: project["id"] as string, token_id: token["id"],
    permissions: token["permissions"], token: token["token"],
  };
  const tenants = load();
  tenants[name] = record;
  // the token is shown once, so it is stored here at that moment
  save(tenants);
  return record;
}

/** The stored record for one tenant. */
export function tenant(name: string): Tenant {
  const record = load()[name];
  if (!record) throw new Error(`${name} has not been onboarded`);
  return record;
}

/** A client that authenticates as the tenant. Never falls back to yours. */
export function asTenant(record: Partial<Tenant>): RestClient {
  if (!record.project_id || !record.token) {
    throw new Error("no tenant credentials; refusing to act as the platform");
  }
  return new RestClient({ project: record.project_id, token: record.token, host: SPACE });
}

/** Numbers the tenant can pick from. Returns E.164 strings. */
export async function offer(record: Tenant, areacode: string, maxResults = 5) {
  // the spec's query param is `areacode`, all lower case. The SDK passes the
  // keys through, so a camelCase one would travel undocumented
  const found = await asTenant(record).phoneNumbers.search({
    areacode, number_type: "local", max_results: maxResults,
  });
  return (found["data"] ?? []).map((n: Record<string, string>) => n["number"]);
}

/** Purchase the number into the tenant's subproject and point it at them. */
export async function buy(record: Tenant, number: string, webhookUrl: string) {
  const client = asTenant(record);
  const bought = await client.phoneNumbers.create({ number });
  await client.phoneNumbers.update(bought["id"], {
    name: record.name, call_handler: "relay_script", call_relay_script_url: webhookUrl,
  });
  return bought;
}

/** The first page of the tenant's numbers. Page with `page_size`. */
export function numbers(record: Tenant) {
  return asTenant(record).phoneNumbers.list();
}

/** Give the number back when the tenant cancels. */
export function release(record: Tenant, numberId: string) {
  return asTenant(record).phoneNumbers.delete(numberId);
}

if (process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, "/"))) {
  const [cmd, name, ...rest] = process.argv.slice(2);
  if (!name) {
    console.log("usage: npm start <onboard|offer|buy|numbers|release> <tenant> [args]");
  } else if (cmd === "onboard") {
    console.log(await onboard(name));
  } else if (cmd === "offer") {
    for (const n of await offer(tenant(name), rest[0])) console.log(n);
  } else if (cmd === "buy") {
    console.log(await buy(tenant(name), rest[0], rest[1]));
  } else if (cmd === "numbers") {
    console.log(await numbers(tenant(name)));
  } else if (cmd === "release") {
    console.log(await release(tenant(name), rest[0]));
  }
}
