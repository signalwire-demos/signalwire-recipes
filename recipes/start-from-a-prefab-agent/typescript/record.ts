/**
 * The recorder verify.py drives. It builds both prefabs, renders each document,
 * and calls their tools through the agents' own /swaig routes with the
 * rendered global_data, as the platform would. Expected values live in
 * verify.py, next to the Python surface's.
 */
import { SurveyAgent, type AgentBase } from "@signalwire/sdk";

const recipe = await import("./index.js");
const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");

type Step = Record<string, Record<string, unknown>>;
type Doc = { sections: { main: Step[] } };
type Json = Record<string, unknown>;

function aiOf(agent: AgentBase) {
  const doc = JSON.parse(agent.renderSwml()) as Doc;
  return { doc, ai: doc.sections.main.find((s) => "ai" in s)!["ai"] as Json };
}

async function tool(agent: AgentBase, route: string, name: string, args: Json, global: Json) {
  const res = await agent.getApp().fetch(new Request(`http://local${route}/swaig`, {
    method: "POST", headers: { Authorization: auth, "content-type": "application/json" },
    body: JSON.stringify({ function: name, call_id: "c1", global_data: global,
                           argument: { parsed: [args], raw: JSON.stringify(args) } }),
  }));
  return res.json();
}

// --- receptionist ---------------------------------------------------------
const rec = recipe.buildReceptionist();
const reception = aiOf(rec);
const global = { ...(reception.ai["global_data"] as Json) };
const collected = await tool(rec, "/reception", "collect_caller_info",
                             { name: "Dana Whitfield", reason: "a squeaky brake" }, global);
global["caller_info"] = { name: "Dana Whitfield" };
const transferred = await tool(rec, "/reception", "transfer_call",
                               { department: "workshop" }, global);
const refused = await tool(rec, "/reception", "transfer_call", { department: "legal" }, global);

// --- survey ---------------------------------------------------------------
const sv = recipe.buildSurvey();
const survey = aiOf(sv);
const sglobal = survey.ai["global_data"] as Json;
const answer = (name: string, response: string) =>
  tool(sv, "/survey", name, { question_id: "rating", response }, sglobal);
const outOfScale = await answer("validate_response", "7");
const valid = await answer("validate_response", "4");
const logged = await answer("log_response", "4");

// what the constructor does with an incomplete question, and with the fourth type
const lax = new SurveyAgent({ surveyName: "s", name: "lax", route: "/lax", questions: [
  { id: "r", type: "rating", text: "Rate it." },
  { id: "c", type: "multiple_choice", text: "Which shop?", options: ["north", "south"] },
] });
const laxQuestions = (aiOf(lax).ai["global_data"] as Json)["questions"];
let missingOptions = "";
try {
  new SurveyAgent({ surveyName: "s", name: "bad", route: "/bad",
                    questions: [{ id: "c", type: "multiple_choice", text: "Pick." }] });
} catch (error) {
  missingOptions = (error as Error).message;
}

console.log(JSON.stringify({
  reception: reception.doc, collected, transferred, refused,
  survey: survey.doc, outOfScale, valid, logged, laxQuestions, missingOptions,
}));
