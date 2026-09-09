/**
 * The recorder verify.py drives. It replaces fetch, creates the script and
 * points a number at it through the same helpers the page shows, then tries a
 * number the project does not hold, and prints what it captured as JSON.
 * Expected values live in verify.py.
 */
type Captured = { method: string; path: string; query: string; body: unknown };
const captured: Captured[] = [];
const [scriptId = "", url = "", number = "", nid = "", near = "",
       nearId = ""] = process.argv.slice(2);
// the listing answers with a longer neighbour first: filter_number is a
// contains match, so the recipe has to pick the exact number
const responses: unknown[] = [
  { id: scriptId, type: "cxml_script", cxml_script: { request_url: url } },
  { data: [{ id: nearId, number: near }, { id: nid, number }] },
  {},
  { data: [{ id: nearId, number: near }] },
];

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
const created = await recipe.create();
await recipe.pointNumber(created[0], number);
const happy = captured.length;

let refused = false;
try {
  await recipe.pointNumber(created[0], number);
} catch (error) {
  refused = String((error as Error).message).includes(number);
}
const absent = { refused, methods: captured.slice(happy).map((c) => c.method) };
console.log(JSON.stringify({ captured: captured.slice(0, happy), created, absent }));
