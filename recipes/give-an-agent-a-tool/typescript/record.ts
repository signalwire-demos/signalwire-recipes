/**
 * The recorder verify.py drives. It renders the agent's document, then calls
 * the tool through the agent's own /swaig route, as the platform would, for a
 * known and an unknown order, and prints both as JSON. Expected values live in
 * verify.py, next to the Python surface's.
 */
const recipe = await import("./index.js");
const [known = "48815", unknown = "00000"] = process.argv.slice(2);
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");

const agent = new recipe.OrderAgent();
const app = agent.getApp();
type Doc = { sections: { main: Record<string, Record<string, unknown>>[] } };
const doc = JSON.parse(agent.renderSwml()) as Doc;
const ai = doc.sections.main.find((s) => "ai" in s)!["ai"];

async function call(orderId: string) {
  const res = await app.fetch(new Request("http://local/orders/swaig", {
    method: "POST", headers: { Authorization: auth, "content-type": "application/json" },
    body: JSON.stringify({ function: "get_order_status", call_id: "c1",
                           argument: { parsed: [{ order_id: orderId }], raw: "{}" } }),
  }));
  return { status: res.status, json: await res.json() };
}
const unauthorized = await app.fetch(new Request("http://local/orders/swaig", {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ function: "get_order_status", argument: { parsed: [{}] } }),
}));

console.log(JSON.stringify({ doc, functions: ai["SWAIG"], known: await call(known),
                             unknown: await call(unknown), unauthorized: unauthorized.status }));
