/**
 * The recorder verify.py drives. It replaces fetch, makes the two requests
 * through the same helper the page shows, and prints what it captured as JSON.
 * The expected values live in verify.py, next to the Python surface's.
 */
type Captured = { method: string; path: string; body: unknown };
const captured: Captured[] = [];
const [resourceId = "res-abc"] = process.argv.slice(2);
const responses: unknown[] = [{ id: resourceId }, {}];

// HttpClient captures globalThis.fetch when the client is built, so it is
// replaced before index.ts is imported
globalThis.fetch = (async (input: unknown, init?: RequestInit) => {
  const url = new URL(String(input));
  captured.push({
    method: init?.method ?? "GET",
    path: url.pathname,
    body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
  });
  return new Response(JSON.stringify(responses[captured.length - 1] ?? {}), {
    status: 200, headers: { "content-type": "application/json" },
  });
}) as typeof fetch;

const recipe = await import("./index.js");
const resource = await recipe.pointNumberAt();
console.log(JSON.stringify({ captured, returned: resource }));
