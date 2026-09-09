/**
 * The recorder verify.py drives. It captures the client's fetch, builds the
 * document, deploys the flow and points a number at it, and prints the
 * document and the requests as JSON. Expected values live in verify.py.
 */
type Captured = { method: string; path: string; query: string; body: unknown };
const captured: Captured[] = [];
const [resourceId = "", number = "", nid = ""] = process.argv.slice(2);
const responses: unknown[] = [
  { id: resourceId, type: "call_flow" },
  { data: [{ id: "near-miss", number: `${number}9` }, { id: nid, number }] },
  { id: "route-1" },
];

// HttpClient captures globalThis.fetch when the client is built, so it is
// replaced before index.ts is imported
globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const target = new URL(String(input));
  captured.push({
    method: init?.method ?? "GET",
    path: target.pathname,
    query: target.search,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  return new Response(JSON.stringify(responses[captured.length - 1] ?? {}), {
    status: 200, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

const recipe = await import("./index.js");
const doc = recipe.build().getDocument();
const flow = await recipe.deploy();
await recipe.pointNumber(flow["id"], number);
console.log(JSON.stringify({ doc, captured }));
