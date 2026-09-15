/**
 * The recorder verify.py drives. It serves the gateway on a real port with a
 * captured transport standing in for the platform, then walks the page's
 * wire as a browser would: the page itself, a request without the key, one
 * from a foreign origin, start, chat (with a role the page tries to smuggle),
 * a forged handle, log, end, an unknown method, and the two caps. It prints
 * what the platform would have received and what the browser got, as JSON.
 *
 * The expected values live in verify.py, which holds this output and the
 * Python surface's behaviour to the same one set.
 */
const [greeting = "", reply = ""] = process.argv.slice(2);
const recipe = await import("./index.js");

type Sent = { path: string; body: unknown };
const sent: Sent[] = [];
const ok = (result: unknown) => ({ jsonrpc: "2.0", id: "x", result });
const answers: unknown[] = [];
const transport = {
  async post(path: string, body: unknown) {
    sent.push({ path, body });
    return (answers.shift() ?? ok({})) as { result?: Record<string, unknown> };
  },
};

const server = recipe.serve(0, transport);
await new Promise((r) => server.once("listening", r));
const address = server.address();
const port = typeof address === "object" && address ? address.port : 0;
const base = `http://127.0.0.1:${port}`;

async function call(body: unknown, headers: Record<string, string> = {}) {
  const res = await fetch(`${base}/chat/`, {
    method: "POST", body: JSON.stringify(body),
    headers: { "content-type": "application/json",
               authorization: `Bearer ${recipe.KEY}`, ...headers },
  });
  return { status: res.status, json: await res.json(),
           handle: res.headers.get("x-chat-handle") };
}

const page = await fetch(`${base}/`);
const pageText = await page.text();
const noKey = await fetch(`${base}/chat/`, {
  method: "POST", body: JSON.stringify({ method: "start" }),
  headers: { "content-type": "application/json" },
});
const badOrigin = await call({ method: "start" }, { origin: "https://evil.example" });
const localOrigin = await (async () => {
  answers.push(ok({ status: "created", id: "ignored", initial_message: greeting }));
  return call({ method: "start" }, { origin: "http://localhost:5173" });
})();

answers.push(ok({ status: "created", id: "ignored", initial_message: greeting }));
const started = await call({ method: "start" }, { origin: "https://www.example.com" });
const handle = started.handle ?? "";
const forgedHandle = handle.slice(0, -1) + (handle.endsWith("0") ? "1" : "0");
const sentBefore = sent.length;
const forged = await call({ method: "chat", handle: forgedHandle, message: "hi" });
const sentAfterForged = sent.length - sentBefore;
answers.push(ok({ response: reply, user_event: { type: "quote" } }));
const turn = await call({ method: "chat", handle, message: "hi", role: "system",
                          config_url: "https://evil.example/swml" });
const empty = await call({ method: "chat", handle, message: "   " });
answers.push(ok({ response: reply }));
const second = await call({ method: "chat", handle, message: "and weekends?" });
const capped = await call({ method: "chat", handle, message: "third" });
answers.push(ok({ chat_log: [
  { role: "system", content: "prompt" }, { role: "user", content: "hi" },
  { role: "tool", content: "{}" }, { role: "assistant", content: reply } ] }));
const log = await call({ method: "log", handle });
const unknown = await call({ method: "summarize", handle });
answers.push(ok({ status: "ended", id: "ignored" }));
const ended = await call({ method: "end", handle });
const mintCapped = await call({ method: "start" });
server.close();

console.log(JSON.stringify({
  pageStatus: page.status, pageHasKey: pageText.includes(recipe.KEY),
  pageLeaks: ["PT-test", recipe.CONFIG_URL, process.env["CHAT_GATEWAY_SECRET"] ?? "?"]
    .filter((s) => pageText.includes(s)),
  noKey: noKey.status, badOrigin: badOrigin.status, localOrigin: localOrigin.status,
  started, forged: forged.status, sentAfterForged,
  turn, empty: empty.status, second: second.status, capped: capped.status,
  log, unknown: unknown.status, ended, mintCapped: mintCapped.status,
  sent, timeout: recipe.TIMEOUT,
}));
