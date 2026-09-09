/**
 * The recorder verify.py drives. It renders the document, then runs the same
 * out-of-order sequence the Python verifier runs through the agent's own
 * /swaig route, threading global_data between calls the way the platform
 * does, and prints every result as JSON. Expected values live in verify.py.
 */
const recipe = await import("./index.js");
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");
type Json = Record<string, unknown>;
type Step = { tool: string; args: Json };
const steps = JSON.parse(process.argv[2] ?? "[]") as Step[];

const agent = new recipe.AbsenceLine();
const app = agent.getApp();
type Doc = { sections: { main: Record<string, Json>[] } };
const doc = JSON.parse(agent.renderSwml()) as Doc;

let globalData: Json = {};
const results: Json[] = [];
for (const step of steps) {
  const res = await app.fetch(new Request("http://local/absence/swaig", {
    method: "POST", headers: { Authorization: auth, "content-type": "application/json" },
    body: JSON.stringify({ function: step.tool, call_id: "c1", global_data: globalData,
                           argument: { parsed: [step.args],
                                       raw: JSON.stringify(step.args) } }),
  }));
  const result = (await res.json()) as Json;
  for (const action of (result["action"] as Json[] | undefined) ?? []) {
    if ("set_global_data" in action) {
      globalData = { ...globalData, ...(action["set_global_data"] as Json) };
    }
  }
  results.push(result);
}
console.log(JSON.stringify({ doc, results, globalData, reports: recipe.REPORTS.length }));
