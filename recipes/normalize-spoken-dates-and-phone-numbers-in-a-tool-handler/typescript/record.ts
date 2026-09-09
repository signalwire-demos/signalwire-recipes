/**
 * The recorder verify.py drives. It renders the document, then posts each
 * (date, phone) case from verify.py's table to the agent's own /swaig route
 * and prints every result as JSON. Expected values live in verify.py.
 */
const recipe = await import("./index.js");
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");
type Json = Record<string, unknown>;
const cases = JSON.parse(process.argv[2] ?? "[]") as { date: string; phone: string }[];

const agent = new recipe.CallbackDesk();
const app = agent.getApp();
type Doc = { sections: { main: Record<string, Json>[] } };
const doc = JSON.parse(agent.renderSwml()) as Doc;

const results: Json[] = [];
for (const args of cases) {
  const res = await app.fetch(new Request("http://local/callback/swaig", {
    method: "POST", headers: { Authorization: auth, "content-type": "application/json" },
    body: JSON.stringify({ function: "schedule_callback", call_id: "c1",
                           argument: { parsed: [args], raw: JSON.stringify(args) } }),
  }));
  results.push((await res.json()) as Json);
}
console.log(JSON.stringify({ doc, results }));
