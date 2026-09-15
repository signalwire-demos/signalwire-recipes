"""Prove the claim without a network.

Claim: the agent a phone number reaches is reachable over text through the AI
Chat API, with no second definition. `POST /api/ai/chat` takes a JSON-RPC 2.0
body, `params.config_url` names the URL the agent serves its SWML from, and
the six documented methods create, drive, read, summarise, end and delete a
conversation.

Proof: the agent's real app is driven with `TestClient` and the document it
serves validates. The config URL is that route with a trailing slash on the
public host, carrying the basic-auth pair from the environment. With the HTTP
layer replaced by a recorder, the six helpers send six POSTs to the documented
path, each an envelope with `jsonrpc: "2.0"`, a unique request id, the method
name and params; for every method the params carry the spec's required fields
and nothing the spec does not document, and the role enum is read from the
spec. A role outside the enum is refused before any request. A JSON-RPC error
inside a 200 raises with its code, and a summary failure riding the success
envelope raises rather than returning an empty string. The TypeScript surface
is held to the same bodies. Expected values live here, not in app.py.
"""
import base64
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
USER, PASSWORD = "recipes", "pw"
PUBLIC = "https://abc123.ngrok-free.app"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SWML_BASIC_AUTH_USER": USER,
    "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
    "AGENT_PUBLIC_URL": PUBLIC,
})

import verifylib as V  # noqa: E402

CHAT = "/api/ai/chat"
CID = "text-verifier"
URL = f"https://{USER}:{PASSWORD}@abc123.ngrok-free.app/front-desk/"
GREETING = "Hi, this is Ridgeline Cycles. How can I help?"
REPLY = "We are open Monday to Friday, nine to five, Eastern."
SUMMARY = "The customer asked about opening hours."
METHODS = ["create_conversation", "chat", "chat", "chat_log", "summarize",
           "end_conversation", "delete"]
AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}


def ok(result):
    return {"jsonrpc": "2.0", "id": "x", "result": result}


ANSWERS = [
    ok({"status": "created", "id": CID, "initial_message": GREETING}),
    ok({"response": REPLY, "user_event": {"type": "quote"}}),
    ok({"response": REPLY}),
    ok({"chat_log": [{"role": "system", "content": "prompt"},
                     {"role": "user", "content": "hi"},
                     {"role": "assistant", "content": REPLY}]}),
    ok({"summary": SUMMARY}),
    ok({"status": "ended", "id": CID}),
    ok({"status": "deleted", "id": CID}),
]


def check_bodies(bodies, spec_variants):
    """Every envelope and every params object against the spec, in order."""
    assert [b["method"] for b in bodies] == METHODS, [b["method"] for b in bodies]
    ids = [b["id"] for b in bodies]
    assert len(set(ids)) == len(ids) and all(isinstance(i, str) and i for i in ids), ids
    for body in bodies:
        v = spec_variants[body["method"]]
        assert body["jsonrpc"] == "2.0", body
        assert v["envelope"] <= set(body), (body["method"], sorted(body))
        params = body["params"]
        assert v["required"] <= set(params), (body["method"], sorted(params))
        assert set(params) <= set(v["documented"]), (body["method"], sorted(params))
        assert params["id"] == CID, params
    create, first, steered, log, summ, end, delete = (b["params"] for b in bodies)
    assert create == {"id": CID, "config_url": URL}, create
    assert first == {"id": CID, "message": "hi"}, first
    assert steered == {"id": CID, "message": "Answer in French.", "role": "system"}, steered
    assert log == {"id": CID} and end == {"id": CID} and delete == {"id": CID}
    assert summ == {"id": CID}, summ


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    import app as recipe

    # the agent is the voice agent: its app serves a valid document behind auth
    V.assert_basic_auth_from_env(recipe.agent)
    web = TestClient(recipe.agent.get_app())
    r = web.post("/front-desk/", json={"call": {}}, headers=AUTH)
    assert r.status_code == 200, r.text
    doc = r.json()
    V.validate_swml(doc)
    (ai,) = [s["ai"] for s in doc["sections"]["main"] if "ai" in s]
    assert [s["title"] for s in ai["prompt"]["pom"]] == ["Role", "Hours", "Limits"]
    assert web.post("/front-desk/", json={"call": {}}).status_code == 401

    # the config URL is that route, with the slash the SDK registers, plus the pair
    assert recipe.config_url(recipe.agent) == URL, recipe.config_url(recipe.agent)
    assert recipe.config_url(recipe.agent, PUBLIC + "/") == URL

    # six methods, six POSTs, every body inside the spec
    rec = V.Recorder(responses=list(ANSWERS))
    channel = recipe.TextChannel(http=rec)
    made = channel.create(CID, URL)
    assert made["initial_message"] == GREETING, made
    first = channel.say(CID, "hi")
    assert first == {"response": REPLY, "user_event": {"type": "quote"}}, first
    assert channel.say(CID, "Answer in French.", role="system")["response"] == REPLY
    log = channel.log(CID)
    assert [m["role"] for m in log] == ["system", "user", "assistant"], log
    assert channel.summarize(CID) == SUMMARY
    assert channel.end(CID)["status"] == "ended"
    assert channel.delete(CID)["status"] == "deleted"
    assert all(c["method"] == "POST" and c["path"] == CHAT for c in rec.calls), rec.calls
    spec = V.spec("rest")
    sv = V.jsonrpc_variants("rest", CHAT)
    assert set(sv) == set(METHODS), sorted(sv)
    check_bodies([c["body"] for c in rec.calls], sv)
    role = sv["chat"]["documented"]["role"]
    assert role["enum"] == ["user", "system"] and role["default"] == "user", role
    assert list(recipe.ROLES) == role["enum"], recipe.ROLES
    # the two ways out are two methods: one runs the post_prompt, one does not
    assert "post-processing" in spec["paths"][CHAT]["post"]["description"]
    for call in rec.calls:
        assert "PT-test" not in str(call["body"]), "the token rides in auth, not the body"

    # a role outside the enum never reaches the wire
    try:
        channel.say(CID, "x", role="assistant")
    except ValueError:
        pass
    else:
        raise AssertionError("an undocumented role was sent")
    assert len(rec.calls) == len(METHODS), len(rec.calls)

    # a JSON-RPC error rides an HTTP 200; the helper raises with the code
    rec2 = V.Recorder(responses=[
        {"jsonrpc": "2.0", "id": "x", "error": {"code": -32001, "message": "unknown"}},
        ok({"error": "generation failed"}),
    ])
    channel = recipe.TextChannel(http=rec2)
    try:
        channel.log("nobody")
    except recipe.ChatError as exc:
        assert exc.code == -32001, exc
    else:
        raise AssertionError("an error envelope was returned as a result")
    try:
        channel.summarize(CID)
    except recipe.ChatError as exc:
        assert "generation failed" in str(exc), exc
    else:
        raise AssertionError("a failed summary returned as text")

    # the TypeScript surface renders its own agent and sends the same bodies
    node = V.node_surface(HERE, CID, PUBLIC, GREETING, REPLY, SUMMARY,
                          env={"SWML_BASIC_AUTH_USER": USER,
                               "SWML_BASIC_AUTH_PASSWORD": PASSWORD})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["status"] == 200, node["status"]
        V.validate_swml(node["doc"])
        assert node["url"] == URL, node["url"]
        assert all(s["method"] == "POST" and s["path"] == CHAT for s in node["sent"])
        check_bodies([s["body"] for s in node["sent"][:len(METHODS)]], sv)
        assert node["made"]["initial_message"] == GREETING, node["made"]
        assert node["first"] == first and node["steered"]["response"] == REPLY, node
        assert [m["role"] for m in node["log"]] == ["system", "user", "assistant"]
        assert node["summarized"] == SUMMARY, node["summarized"]
        assert node["ended"]["status"] == "ended" and node["deleted"]["status"] == "deleted"
        assert node["roleRefused"] is True, node
        assert node["errorCode"] == -32001, node["errorCode"]
        assert node["summaryFailed"] is True, node
        assert len(node["sent"]) == len(METHODS) + 2, len(node["sent"])
        ts_note = ("typescript serves the same document, builds the same config URL, "
                   "sends the same seven envelopes and refuses the same role")

    print(f"ok: the agent's app serves a valid document behind basic auth, the config "
          f"URL is {URL}, and create, two chats, chat_log, summarize, end_conversation "
          f"and delete each POST {CHAT} as a JSON-RPC 2.0 envelope with a unique id "
          f"and params inside the spec; the role enum is {role['enum']} and another "
          f"role is refused before the wire; an error envelope raises with its code "
          f"and a failed summary raises; {ts_note}")


if __name__ == "__main__":
    main()
