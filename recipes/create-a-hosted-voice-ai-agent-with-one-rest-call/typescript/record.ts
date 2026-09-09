/**
 * The recorder verify.py drives. It renders the agent, creates the hosted
 * resource and points a number at it through a captured fetch, then tries a
 * number the project does not hold, and prints what it captured as JSON.
 *
 * The expected values live in verify.py, which holds this output and the Python
 * surface's requests to the same one set.
 */
type Captured = { method: string; path: string; query: string; body: unknown };
const captured: Captured[] = [];
const [agentId = "", main = "", near = "", nid = "", nearId = ""] = process.argv.slice(2);

// the responses the platform would give, in request order
const responses: unknown[] = [
  { id: agentId, display_name: "ridgeline-front-desk", type: "ai_agent" },
  { data: [{ id: nearId, number: near }, { id: nid, number: main }] },
  { id: agentId, type: "ai_agent" },
  { data: [{ id: nearId, number: near }] },
];

// HttpClient captures globalThis.fetch when the client is built, so it is
// replaced before index.ts is imported
globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const url = new URL(String(input));
  captured.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    query: url.search,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  return new Response(JSON.stringify(responses[captured.length - 1] ?? {}), {
    status: 200, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

process.env["SWML_BASIC_AUTH_USER"] = "u";
process.env["SWML_BASIC_AUTH_PASSWORD"] = "p";
const recipe = await import("./index.js");

await recipe.create();
await recipe.pointNumber(agentId, main);

let refused = false;
try {
  await recipe.pointNumber(agentId, main);
} catch (error) {
  refused = String((error as Error).message).includes(main);
}

console.log(JSON.stringify({ captured: captured.slice(0, 3), refused,
                             afterRefusal: captured.slice(3).map((c) => c.method) }));
