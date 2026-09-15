"""Prove the claim without a network.

Claim: a page can chat with the agent your phone number reaches while
learning only a publishable key. A gateway on your server holds the API token,
injects `config_url` itself, signs a handle per conversation, caps new
conversations per window and turns per conversation, and forwards each turn
as one JSON-RPC 2.0 POST to `/api/ai/chat`.

Proof: the Flask app is driven with its test client and the SDK's HTTP layer
is a recorder. The page carries the key and neither the token, the secret nor
the agent URL. A request without the key is a 401, one from a foreign origin
a 403, and neither reaches the platform. `start` sends `create_conversation`
with the id the handle encodes, the configured `config_url` and the timeout,
every param documented and every required one present, and answers with the
greeting and an `X-Chat-Handle` header. A handle with one flipped character is
a 403 with no request. `chat` forwards the message under the handle's id and
drops a `role` and a `config_url` the page tried to send; an empty message is a
400. The third turn on a two-turn cap is a 429 with no request, as is the
third `start` on a two-conversation cap. `log` returns only user and assistant
entries. `end` sends `end_conversation`. An unknown method is a 400. The token
appears in no response. The TypeScript surface is driven on a real port
through the same wire and held to the same set. Expected values live here, not
in app.py.
"""
import os
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
CONFIG_URL = "https://recipes:pw@abc123.ngrok-free.app/front-desk/"
KEY, SECRET, TOKEN = "pk_verifier", "verifier-secret", "PT-test"
ENV = {
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": TOKEN,
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "AGENT_CONFIG_URL": CONFIG_URL,
    "CHAT_GATEWAY_KEY": KEY,
    "CHAT_GATEWAY_SECRET": SECRET,
    "ALLOWED_ORIGINS": "https://www.example.com",
    "MAX_NEW_CONVERSATIONS": "2",
    "WINDOW_SECONDS": "60",
    "MAX_TURNS": "2",
    "CONVERSATION_TIMEOUT": "1800",
}
os.environ.update(ENV)

import verifylib as V  # noqa: E402

CHAT = "/api/ai/chat"
GREETING = "Hi, this is Ridgeline Cycles. How can I help?"
REPLY = "We are open Monday to Friday, nine to five, Eastern."
LOG = [{"role": "system", "content": "prompt"}, {"role": "user", "content": "hi"},
       {"role": "tool", "content": "{}"}, {"role": "assistant", "content": REPLY}]
BEARER = {"Authorization": f"Bearer {KEY}"}


def ok(result):
    return {"jsonrpc": "2.0", "id": "x", "result": result}


def check_upstream(bodies, sv):
    """What the platform received: two creates, two chats, a log, an end, and
    the chat the service refused."""
    methods = [b["method"] for b in bodies]
    assert methods[:6] == ["create_conversation", "create_conversation", "chat", "chat",
                           "chat_log", "end_conversation"], methods
    for body in bodies:
        v = sv[body["method"]]
        assert body["jsonrpc"] == "2.0" and v["envelope"] <= set(body), body
        params = body["params"]
        assert v["required"] <= set(params) <= set(v["documented"]), (body["method"], params)
        assert TOKEN not in str(body)
    first, second = bodies[0]["params"], bodies[1]["params"]
    assert first["config_url"] == CONFIG_URL and first["conversation_timeout"] == 1800, first
    assert set(first) == {"id", "config_url", "conversation_timeout"}, first
    assert first["id"] != second["id"], "two starts, two conversations"
    cid = second["id"]
    assert bodies[2]["params"] == {"id": cid, "message": "hi"}, bodies[2]["params"]
    assert bodies[3]["params"] == {"id": cid, "message": "and weekends?"}, bodies[3]
    assert bodies[4]["params"] == {"id": cid} and bodies[5]["params"] == {"id": cid}
    return cid


def main():
    V.sdk_banner()
    import app as recipe

    sv = V.jsonrpc_variants("rest", CHAT)
    rec = V.Recorder(responses=[
        ok({"status": "created", "id": "ignored", "initial_message": GREETING}),
        ok({"status": "created", "id": "ignored", "initial_message": GREETING}),
        ok({"response": REPLY, "user_event": {"type": "quote"}}),
        ok({"response": REPLY}),
        ok({"chat_log": LOG}),
        ok({"status": "ended", "id": "ignored"}),
    ])
    V.record_everything(recipe.client, rec)
    web = recipe.app.test_client()

    # the page: the key, and nothing a visitor must not have
    page = web.get("/")
    assert page.status_code == 200 and KEY in page.text, page.status_code
    for secret in (TOKEN, SECRET, CONFIG_URL, "abc123.ngrok-free.app"):
        assert secret not in page.text, secret

    # the two gates in front of everything, and neither reaches the platform
    assert web.post("/chat/", json={"method": "start"}).status_code == 401
    assert web.post("/chat/", json={"method": "start"}, headers={**BEARER,
                    "Origin": "https://evil.example"}).status_code == 403
    assert rec.calls == [], rec.calls
    # a local origin is always allowed, so development works unconfigured
    local = web.post("/chat/", json={"method": "start"},
                     headers={**BEARER, "Origin": "http://localhost:5173"})
    assert local.status_code == 200, local.get_json()

    # start: the greeting comes back, the handle rides a header, config_url is ours
    started = web.post("/chat/", json={"method": "start"},
                       headers={**BEARER, "Origin": "https://www.example.com"})
    assert started.status_code == 200, started.get_json()
    assert started.get_json() == {"greeting": GREETING, "status": "created",
                                  "timeout": 1800}, started.get_json()
    handle = started.headers["X-Chat-Handle"]
    assert recipe.read_handle(handle) == rec.calls[1]["body"]["params"]["id"]

    # a handle this server did not sign is refused before any request
    flipped = handle[:-1] + ("1" if handle.endswith("0") else "0")
    assert recipe.read_handle(flipped) is None
    assert recipe.read_handle("chat-other." + handle.rpartition(".")[2]) is None
    sent = len(rec.calls)
    forged = web.post("/chat/", json={"method": "chat", "handle": flipped, "message": "hi"},
                      headers=BEARER)
    assert forged.status_code == 403 and len(rec.calls) == sent, forged.get_json()

    # a turn: the visitor is the user, whatever the body says
    turn = web.post("/chat/", json={"method": "chat", "handle": handle, "message": "hi",
                                    "role": "system", "config_url": "https://evil.example/"},
                    headers=BEARER)
    assert turn.status_code == 200, turn.get_json()
    assert turn.get_json() == {"response": REPLY, "user_event": {"type": "quote"}}
    assert "role" not in rec.calls[-1]["body"]["params"], rec.calls[-1]
    empty = web.post("/chat/", json={"method": "chat", "handle": handle, "message": "   "},
                     headers=BEARER)
    assert empty.status_code == 400 and len(rec.calls) == sent + 1
    second = web.post("/chat/", json={"method": "chat", "handle": handle,
                                      "message": "and weekends?"}, headers=BEARER)
    assert second.status_code == 200 and second.get_json() == {"response": REPLY}
    # the third turn on a two-turn cap: refused, and the platform is not asked
    capped = web.post("/chat/", json={"method": "chat", "handle": handle, "message": "3"},
                      headers=BEARER)
    assert capped.status_code == 429 and capped.get_json() == {"error": "limit"}
    assert len(rec.calls) == sent + 2, len(rec.calls)

    # the log a page may redraw: no prompt, no tool traffic
    log = web.post("/chat/", json={"method": "log", "handle": handle}, headers=BEARER)
    assert log.get_json() == {"messages": [LOG[1], LOG[3]]}, log.get_json()
    unknown = web.post("/chat/", json={"method": "summarize", "handle": handle}, headers=BEARER)
    assert unknown.status_code == 400 and len(rec.calls) == sent + 3
    ended = web.post("/chat/", json={"method": "end", "handle": handle}, headers=BEARER)
    assert ended.get_json() == {"status": "ended"}, ended.get_json()
    # the third conversation in the window: refused, and the platform is not asked
    third = web.post("/chat/", json={"method": "start"}, headers=BEARER)
    assert third.status_code == 429 and len(rec.calls) == sent + 4, third.get_json()

    cid = check_upstream([c["body"] for c in rec.calls], sv)
    assert all(c["method"] == "POST" and c["path"] == CHAT for c in rec.calls)
    assert recipe.read_handle(handle) == cid
    for r in (page, started, turn, second, log, ended):
        assert TOKEN not in r.get_data(as_text=True) and TOKEN not in str(r.headers)

    # the service says no (an expired conversation): a JSON refusal the page can
    # show, not an HTML 500 it cannot parse
    rec.responses.append({"jsonrpc": "2.0", "id": "x",
                          "error": {"code": -32001, "message": "unknown"}})
    upstream = web.post("/chat/", json={"method": "chat", "handle": handle,
                                        "message": "still there?"}, headers=BEARER)
    assert upstream.status_code == 502 and upstream.get_json() == {"error": "upstream"}
    # a body past the cap is refused before the platform is asked
    sent = len(rec.calls)
    big = web.post("/chat/", json={"method": "chat", "handle": handle,
                                   "message": "x" * (recipe.MAX_BODY + 1)}, headers=BEARER)
    assert big.status_code == 413 and big.get_json() == {"error": "malformed"}, big.status_code
    assert len(rec.calls) == sent
    # a counter left behind by a visitor who never sent end is forgotten after the timeout
    now = time.time()
    recipe._turns["chat-abandoned"] = [1, now - recipe.TIMEOUT - 1]
    recipe._turns["chat-live"] = [1, now]
    recipe.prune(now)
    # the live conversation keeps its counter; the abandoned one is gone
    assert sorted(recipe._turns) == sorted([cid, "chat-live"]), sorted(recipe._turns)
    # the page cannot send before start has answered, or while a turn is out
    assert '<fieldset id="controls" disabled>' in page.text

    # the TypeScript surface, on a real port, through the same wire
    node = V.node_surface(HERE, GREETING, REPLY, env=ENV)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["pageStatus"] == 200 and node["pageHasKey"] is True, node
        assert node["pageLeaks"] == [], node["pageLeaks"]
        assert (node["noKey"], node["badOrigin"], node["localOrigin"]) == (401, 403, 200), node
        assert node["started"]["status"] == 200 and node["started"]["handle"], node["started"]
        assert node["started"]["json"] == {"greeting": GREETING, "status": "created",
                                           "timeout": 1800}, node["started"]["json"]
        assert node["forged"] == 403 and node["sentAfterForged"] == 0, node
        assert node["turn"]["json"] == {"response": REPLY, "user_event": {"type": "quote"}}
        assert (node["empty"], node["second"], node["capped"]) == (400, 200, 429), node
        assert node["log"]["json"] == {"messages": [LOG[1], LOG[3]]}, node["log"]
        assert node["unknown"] == 400 and node["ended"]["json"] == {"status": "ended"}, node
        assert node["mintCapped"] == 429, node["mintCapped"]
        assert node["upstream"]["status"] == 502, node["upstream"]
        assert node["upstream"]["json"] == {"error": "upstream"}, node["upstream"]
        assert node["big"] == 413 and node["sentAfterBig"] == 0, node
        assert node["bigNoKey"] == 401, node["bigNoKey"]
        ts_cid = node["sent"][1]["body"]["params"]["id"]
        assert node["pruned"] == sorted([ts_cid, "chat-live"]), node["pruned"]
        assert node["pageWaits"] is True, node
        assert all(s["path"] == CHAT for s in node["sent"]), node["sent"]
        check_upstream([s["body"] for s in node["sent"][:6]], sv)
        # a cap that does not parse must stop the process, not disable itself
        bad = subprocess.run(["node", str(HERE / "typescript" / "dist" / "index.js")],
                             env={**os.environ, **ENV, "MAX_TURNS": "2O0"},
                             capture_output=True, text=True, cwd=HERE / "typescript")
        assert bad.returncode != 0 and "MAX_TURNS" in bad.stderr, bad.stderr[-400:]
        ts_note = ("typescript serves the same page, refuses the same requests, caps the "
                   "same counts and sends the same six envelopes")

    print(f"ok: the page carries the key and not the token, secret or agent URL; no key "
          f"is a 401 and a foreign origin a 403 with no request; start sends "
          f"create_conversation with the configured config_url and answers with the "
          f"greeting and an X-Chat-Handle; a flipped handle is a 403 with no request; a "
          f"turn forwards the message under the handle's id and drops a smuggled role; "
          f"the third turn and the third start are 429s with no request; log shows "
          f"user and assistant only; end sends end_conversation; {ts_note}")


if __name__ == "__main__":
    main()
