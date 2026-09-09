/**
 * The recorder verify.py drives.
 *
 * `HttpClient` captures `globalThis.fetch` when a client is constructed, so
 * replacing it before anything is built records every request from every
 * client, platform and tenant alike. Each captured request carries the basic
 * auth pair it was sent with, which is stronger proof than the constructor
 * arguments: it says who the platform would have seen.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

type Captured = {
  method: string; path: string; query: string; body: unknown; project: string;
};
const captured: Captured[] = [];

const [tenantName = "", projectId = "", tokenId = "", token = "", number = "", hook = ""] =
  process.argv.slice(2);

const responses: unknown[] = [
  { id: projectId, name: tenantName, subproject: true },
  { id: tokenId, name: `${tenantName} numbers`,
    permissions: ["numbers", "calling", "messaging"], token },
  { data: [{ number, region: "CA", city: "SAN FRANCISCO" }] },
  { id: "number-1", number, number_type: "longcode" },
  { id: "number-1", number, call_handler: "relay_script", name: tenantName },
  { data: [{ id: "number-1", number }] },
  {},
];

globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const url = new URL(String(input));
  const headers = (init?.headers ?? {}) as Record<string, string>;
  const auth = headers["Authorization"] ?? headers["authorization"] ?? "";
  captured.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    query: url.search,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
    // the identity the platform would see, read back out of the header
    project: Buffer.from(auth.replace("Basic ", ""), "base64").toString().split(":")[0],
  });
  return new Response(JSON.stringify(responses[captured.length - 1] ?? {}), {
    status: 200, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

// the store is a temporary file: the recipe's own tenants.json is never touched
process.env["TENANTS_PATH"] = join(mkdtempSync(join(tmpdir(), "recipe-")), "tenants.json");

// imported after the env and the fetch are in place, because index.ts builds
// the platform client at module level
const recipe = await import("./index.js");

const record = await recipe.onboard(tenantName);
const onboardingRequests = captured.length;

// a record with no token is refused, and builds no client
const refused: string[] = [];
for (const broken of [{ name: tenantName, project_id: projectId, token: "" },
                      { name: tenantName, project_id: "", token }]) {
  try {
    recipe.asTenant(broken);
    refused.push("BUILT");
  } catch (error) {
    refused.push(String((error as Error).message));
  }
}

const stored = recipe.tenant(tenantName);
const offered = await recipe.offer(stored, "415");
const bought = await recipe.buy(stored, number, hook);
const listed = await recipe.numbers(stored);
await recipe.release(stored, "number-1");

console.log(JSON.stringify({
  record, refused, offered, bought, listed, onboardingRequests, captured,
  permissions: recipe.PERMISSIONS,
}));
