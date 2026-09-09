"""Prove the claim without a network.

Claim: with `save_conversation` on and a `conversation_id` derived from the
caller, the document the agent serves asks the platform to post a summary at
the end of the call, and the same post-prompt route answers the next call's
`fetch_conversation` with that summary.

Proof: the agent's real app is driven with `TestClient`. A SWML request whose
body carries `call.from` renders `ai.params` with `save_conversation: true`, a
`conversation_id` built from the caller, a `post_prompt` and a `post_prompt_url`
ending in the post-prompt route; the document validates. A post-conversation
POST stores the summary in the file. After a module reload, because the save
and the fetch are different requests, a `fetch_conversation` POST for that id
returns `{"conversation_summary": ...}` and an unknown id returns `{}`; an
unauthenticated POST is a 401. Two callers keep two summaries. The TypeScript
surface renders the same params and answers the same two POSTs from its own
post-prompt handler. Expected values live here, not in app.py.
"""
import base64
import importlib
import json
import os
import pathlib
import sys
import tempfile
import urllib.parse

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
MEMORY = pathlib.Path(tempfile.mkdtemp()) / "caller-memory.json"
USER, PASSWORD = "recipes", "pw"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SWML_BASIC_AUTH_USER": USER,
    "SWML_BASIC_AUTH_PASSWORD": PASSWORD,
    "MEMORY_PATH": str(MEMORY),
})

import verifylib as V  # noqa: E402

DANA, LEE = "+14155550123", "+14155550999"
DANA_ID, LEE_ID = "caller-14155550123", "caller-14155550999"
DANA_SUMMARY = "Dana asked about a tune-up next week and prefers mornings."
LEE_SUMMARY = "Lee wanted a price on a child seat."
AUTH = {"Authorization": "Basic " + base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()}


def swml_request(caller):
    """The documented inbound-call payload, as far as the callback reads it."""
    return {"call": {"call_id": "c-1", "node_id": "n", "segment_id": "s",
                     "call_state": "created", "direction": "inbound", "type": "phone",
                     "from": caller, "to": "+15551230000", "headers": [],
                     "project_id": "proj-1234", "space_id": "sp-1"},
            "vars": {}, "envs": {}, "params": {}}


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    import app as recipe

    V.assert_basic_auth_from_env(recipe.agent)
    web = TestClient(recipe.agent.get_app())

    # the document the caller's request renders
    r = web.post("/front-desk/", json=swml_request(DANA), headers=AUTH)
    assert r.status_code == 200, r.text
    doc = r.json()
    V.validate_swml(doc)
    (ai,) = [s["ai"] for s in doc["sections"]["main"] if "ai" in s]
    assert ai["params"]["save_conversation"] is True, ai["params"]
    assert ai["params"]["conversation_id"] == DANA_ID, ai["params"]
    assert ai["post_prompt"]["text"].startswith("Summarise the call"), ai["post_prompt"]
    assert ai["post_prompt_url"].split("?")[0].rstrip("/").endswith("/front-desk/post_prompt"), ai
    # the platform gets only the URL, so the credentials travel inside it
    assert f"//{USER}:{PASSWORD}@" in ai["post_prompt_url"], ai["post_prompt_url"]
    assert [s["title"] for s in ai["prompt"]["pom"]] == ["Role", "Memory"], ai["prompt"]

    # a different caller gets a different conversation id
    other = web.post("/front-desk/", json=swml_request(LEE), headers=AUTH).json()
    (ai2,) = [s["ai"] for s in other["sections"]["main"] if "ai" in s]
    assert ai2["params"]["conversation_id"] == LEE_ID, ai2["params"]
    # and the deployed agent is unchanged: no id without a caller
    plain = web.post("/front-desk/", json={"call": {}}, headers=AUTH).json()
    (ai3,) = [s["ai"] for s in plain["sections"]["main"] if "ai" in s]
    assert "conversation_id" not in ai3.get("params", {}), ai3.get("params")
    # a caller with no digits gets no memory, rather than one every such caller shares
    for anonymous in ("anonymous", "Anonymous", "sip:private@example.com"):
        assert recipe.conversation_id(anonymous) is None, anonymous
    anon = web.post("/front-desk/", json=swml_request("anonymous"), headers=AUTH).json()
    (ai4,) = [s["ai"] for s in anon["sections"]["main"] if "ai" in s]
    assert "conversation_id" not in ai4.get("params", {}), ai4.get("params")
    assert "save_conversation" not in ai4.get("params", {}), ai4.get("params")

    # end of call: the platform posts the summary, and it lands in the file
    for cid, text in ((DANA_ID, DANA_SUMMARY), (LEE_ID, LEE_SUMMARY)):
        saved = web.post("/front-desk/post_prompt", headers=AUTH,
                         json={"action": "post_conversation", "conversation_id": cid,
                               "call_id": "c-1", "post_prompt_data": {"raw": text}})
        assert saved.status_code == 200 and saved.json() == {"success": True}, saved.text
    assert json.loads(MEMORY.read_text(encoding="utf-8")) == {DANA_ID: DANA_SUMMARY,
                                                              LEE_ID: LEE_SUMMARY}

    # next call: a different request to a fresh process asks for the summary
    recipe = importlib.reload(recipe)
    web = TestClient(recipe.agent.get_app())
    fetched = web.post("/front-desk/post_prompt", headers=AUTH,
                       json={"action": "fetch_conversation", "conversation_id": DANA_ID,
                             "call_id": "c-2"})
    assert fetched.status_code == 200, fetched.text
    assert fetched.json() == {"conversation_summary": DANA_SUMMARY}, fetched.json()
    nobody = web.post("/front-desk/post_prompt", headers=AUTH,
                      json={"action": "fetch_conversation",
                            "conversation_id": "caller-000", "call_id": "c-3"})
    assert nobody.json() == {}, nobody.json()
    # the file is a record, not a queue: a fetch changes nothing
    assert json.loads(MEMORY.read_text(encoding="utf-8"))[DANA_ID] == DANA_SUMMARY
    # and nobody without the credentials reads a caller's history
    assert web.post("/front-desk/post_prompt", json={"action": "fetch_conversation",
                    "conversation_id": DANA_ID}).status_code == 401

    # the TypeScript surface renders the same params and answers the same posts
    # a password with a literal % must survive the URL: the platform's client
    # decodes the URL before it builds Basic auth
    ts_password = "pw%41-x"
    node = V.node_surface(HERE, DANA, LEE, DANA_SUMMARY,
                          env={"SWML_BASIC_AUTH_USER": USER,
                               "SWML_BASIC_AUTH_PASSWORD": ts_password})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert node["params"]["save_conversation"] is True, node["params"]
        assert node["params"]["conversation_id"] == DANA_ID, node["params"]
        assert node["otherId"] == LEE_ID, node
        assert node["postPromptUrl"].rstrip("/").endswith("/post_prompt"), node
        parts = urllib.parse.urlsplit(node["postPromptUrl"])
        assert (urllib.parse.unquote(parts.username or ""),
                urllib.parse.unquote(parts.password or "")) == (USER, ts_password), parts
        assert "%2541" in node["postPromptUrl"], node["postPromptUrl"]
        assert "conversation_id" not in node["anonParams"], node["anonParams"]
        assert node["saved"] == {"success": True}, node
        assert node["fetched"] == {"conversation_summary": DANA_SUMMARY}, node
        assert node["unknown"] == {}, node
        assert node["unauthorized"] == 401, node
        ts_note = ("typescript renders the same two params per caller and its own "
                   "post-prompt handler saves, answers the fetch, and refuses a call "
                   "without credentials")

    print(f"ok: the caller's request renders save_conversation true and "
          f"conversation_id {DANA_ID}, a second caller gets {LEE_ID}, and no caller "
          f"gets none; post_conversation stores the summary, and after a reload "
          f"fetch_conversation returns it as conversation_summary, an unknown id gets "
          f"an empty object, and an unauthenticated fetch is a 401; a caller with no "
          f"digits gets no conversation id, and the post_prompt_url carries the "
          f"credentials; {ts_note}")


if __name__ == "__main__":
    main()
