/**
 * The recorder verify.py drives. It renders the agent through its own app,
 * builds the config URL, runs the six methods through a captured transport
 * with the platform's answers scripted, tries a role outside the enum and an
 * error envelope, and prints all of it as JSON.
 *
 * The expected values live in verify.py, which holds this output and the
 * Python surface's requests to the same one set.
 */
const [cid = "", publicBase = "", greeting = "", reply = "", summary = ""] =
  process.argv.slice(2);
const recipe = await import("./index.js");

type Sent = { method: string; path: string; body: unknown };
const sent: Sent[] = [];
const answers: unknown[] = [
  { jsonrpc: "2.0", id: "x",
    result: { status: "created", id: cid, initial_message: greeting } },
  { jsonrpc: "2.0", id: "x", result: { response: reply, user_event: { type: "quote" } } },
  { jsonrpc: "2.0", id: "x", result: { response: reply } },
  { jsonrpc: "2.0", id: "x", result: { chat_log: [
    { role: "system", content: "prompt" }, { role: "user", content: "hi" },
    { role: "assistant", content: reply } ] } },
  { jsonrpc: "2.0", id: "x", result: { summary } },
  { jsonrpc: "2.0", id: "x", result: { status: "ended", id: cid } },
  { jsonrpc: "2.0", id: "x", result: { status: "deleted", id: cid } },
  { jsonrpc: "2.0", id: "x", error: { code: -32001, message: "unknown conversation" } },
  { jsonrpc: "2.0", id: "x", result: { error: "generation failed" } },
];
const transport = {
  async post(path: string, body: unknown) {
    sent.push({ method: "POST", path, body });
    return answers[sent.length - 1] as { jsonrpc: "2.0"; id: string };
  },
};

const user = process.env["SWML_BASIC_AUTH_USER"] ?? "";
const password = process.env["SWML_BASIC_AUTH_PASSWORD"] ?? "";
const auth = "Basic " + Buffer.from(`${user}:${password}`).toString("base64");
const res = await recipe.agent.getApp().fetch(new Request("http://local/front-desk/", {
  method: "POST", headers: { Authorization: auth, "content-type": "application/json" },
  body: JSON.stringify({ call: {} }),
}));
const doc = await res.json();

const channel = new recipe.TextChannel(transport);
const url = recipe.configUrl(recipe.agent, publicBase);
const made = await channel.create(cid, url);
const first = await channel.say(cid, "hi");
const steered = await channel.say(cid, "Answer in French.", "system");
const log = await channel.log(cid);
const summarized = await channel.summarize(cid);
const ended = await channel.end(cid);
const deleted = await channel.delete(cid);

let roleRefused = false;
const before = sent.length;
try {
  await channel.say(cid, "x", "assistant" as never);
} catch (error) {
  roleRefused = !(error instanceof recipe.ChatError) && sent.length === before;
}
let errorCode: number | null | undefined;
try { await channel.log("nobody"); } catch (error) {
  if (error instanceof recipe.ChatError) errorCode = error.code;
}
let summaryFailed = false;
try { await channel.summarize(cid); } catch (error) {
  summaryFailed = error instanceof recipe.ChatError;
}

console.log(JSON.stringify({
  status: res.status, doc, url, sent, made, first, steered, log, summarized,
  ended, deleted, roleRefused, errorCode, summaryFailed,
}));
