"""Prove the claim without a network.

Claim: with debug events enabled, the rendered document tells the platform to
POST every event the configured level selects to the agent's own /debug_events
route. The handler registered with on_debug_event receives each one.

Proof: render and assert `params.debug_webhook_url` points at the agent's
/debug_events route and `params.debug_webhook_level` is what was configured,
at level 1 and again at level 2. Then drive the agent's own HTTP app with
FastAPI's test client and POST events the way the platform does. The handler
receives the label and the full body. An `llm_error` is recorded on its own
list. A POST without basic auth is refused and reaches no handler. A GET is
refused.
The plain-SWML surface validates with the same two params. Expected values
live here, not in app.py.
"""
import base64
import importlib
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")


def basic_auth():
    raw = f"{os.environ['SWML_BASIC_AUTH_USER']}:{os.environ['SWML_BASIC_AUTH_PASSWORD']}"
    return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}


def params_of(agent):
    doc = json.loads(agent._render_swml(call_id="c1"))
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    return ai["params"]


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    os.environ["DEBUG_LEVEL"] = "1"
    import app as recipe

    agent = recipe.agent
    V.assert_basic_auth_from_env(agent)

    # --- the document turns the stream on and points it at this agent ---------
    p = params_of(agent)
    url = p["debug_webhook_url"]
    assert url.split("?")[0].rstrip("/").endswith("/watched/debug_events"), url
    assert p["debug_webhook_level"] == 1, p

    # level 2 is one environment variable away
    os.environ["DEBUG_LEVEL"] = "2"
    recipe2 = importlib.reload(recipe)
    assert params_of(recipe2.agent)["debug_webhook_level"] == 2
    os.environ["DEBUG_LEVEL"] = "1"
    recipe = importlib.reload(recipe)
    agent = recipe.agent

    # --- events arrive at the route and reach the handler ----------------------
    client = TestClient(agent.get_app())
    path = agent.route + "/debug_events"
    del recipe.EVENTS[:]
    del recipe.ERROR_EVENTS[:]

    barge = {"label": "barge", "call_id": "c1", "barge_elapsed_ms": 340}
    r = client.post(path, json=barge)  # no auth
    assert r.status_code == 401, r.status_code
    assert recipe.EVENTS == [], recipe.EVENTS

    r = client.get(path, headers=basic_auth())
    assert r.status_code == 405, r.status_code

    r = client.post(path, json=barge, headers=basic_auth())
    assert r.status_code == 200 and r.json() == {"status": "ok"}, (r.status_code, r.text)
    assert recipe.EVENTS == [("barge", "c1")], recipe.EVENTS
    assert recipe.ERROR_EVENTS == []

    err = {"label": "llm_error", "call_id": "c1", "error": "upstream timeout"}
    r = client.post(path, json=err, headers=basic_auth())
    assert r.status_code == 200
    assert recipe.EVENTS == [("barge", "c1"), ("llm_error", "c1")], recipe.EVENTS
    assert recipe.ERROR_EVENTS == [{"call_id": "c1", "detail": err}], recipe.ERROR_EVENTS

    # an event with no label falls back to its action, per the SDK route
    r = client.post(path, json={"action": "session_end", "call_id": "c1"},
                    headers=basic_auth())
    assert r.status_code == 200 and recipe.EVENTS[-1] == ("session_end", "c1")

    # --- the plain-SWML surface -------------------------------------------------
    y = V.load_yaml(HERE / "swml" / "agent.yaml")
    V.validate_swml(y)
    yp = V.first(y, "ai")["params"]
    assert yp["debug_webhook_url"].endswith("/debug_events"), yp
    assert yp["debug_webhook_level"] == 1, yp

    print(f"ok: params carry debug_webhook_url -> /watched/debug_events at level 1 "
          f"(2 via DEBUG_LEVEL); the route refused no-auth and GET, and the handler "
          f"received {[e[0] for e in recipe.EVENTS]} and recorded one llm_error")


if __name__ == "__main__":
    main()
