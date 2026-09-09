"""Prove the claim without a network.

Claim: every tool webhook request must carry a token minted for that call and
that function. The endpoint refuses a token from another call, for another
function, altered, or expired, and refuses a request with no token or an empty
one. None of those refusals runs a handler.

Proof: drive the agent's own HTTP app with FastAPI's test client, the way the
platform would. Render the document for call A, take the token off the refund
tool's webhook URL, and POST to the tool endpoint under each condition, with
the same basic-auth credentials the URL carries. A handler records every run,
so the verifier proves what was refused never executed. The URLs embed
credentials, so nothing here prints one.
"""
import base64
import json
import os
import pathlib
import sys
from urllib.parse import parse_qs, urlparse

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))

import verifylib as V  # noqa: E402

# what a reader's .env supplies; without it the SDK generates a password that
# exists only in this process and the number's webhook gets a 401
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")
os.environ["TOKEN_TTL_SECONDS"] = "900"

# Expected values live here, not imported from app.py.
TOOLS = ["get_balance", "issue_refund"]
REFUND_OK = "Refunded 42.10 to the card on file for Dana Whitfield."
BALANCE_OK = "Dana Whitfield has a balance of 42.10."
SDK_REFUSAL = "security token for this function is invalid or expired"


def basic_auth():
    raw = f"{os.environ['SWML_BASIC_AUTH_USER']}:{os.environ['SWML_BASIC_AUTH_PASSWORD']}"
    return {"Authorization": "Basic " + base64.b64encode(raw.encode()).decode()}


def swaig_body(function, call_id, **args):
    """The shape the platform POSTs to a tool webhook."""
    return {"function": function, "call_id": call_id,
            "argument": {"parsed": [args], "raw": json.dumps(args)}}


def main():
    V.sdk_banner()
    from fastapi.testclient import TestClient
    import app as recipe

    agent = recipe.agent
    V.assert_basic_auth_from_env(agent)
    client = TestClient(agent.get_app())
    path = agent.route + "/swaig"

    # --- the document for call A carries one token per secure tool ----------
    doc = json.loads(agent._render_swml(call_id="call-A"))
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    fns = {f["function"]: f for f in ai["SWAIG"]["functions"]}
    assert sorted(fns) == TOOLS, sorted(fns)
    tokens = {}
    for name in TOOLS:
        q = parse_qs(urlparse(fns[name]["web_hook_url"]).query)
        assert "__token" in q, f"{name} rendered without a token"
        tokens[name] = q["__token"][0]
    assert tokens["get_balance"] != tokens["issue_refund"], "one token per function"
    # neither tool sets secure=; the tokens are the default
    refund = tokens["issue_refund"]

    def post(token, call_id, function="issue_refund", auth=True):
        url = path + (f"?__token={token}" if token is not None else "")
        r = client.post(url, json=swaig_body(function, call_id, account_id="48815"),
                        headers=basic_auth() if auth else {})
        return r.status_code, r.json()

    runs = recipe.HANDLER_RUNS

    # --- basic auth still gates the route -----------------------------------
    status, _ = post(refund, "call-A", auth=False)
    assert status == 401, status
    assert runs == [], runs

    # --- the token, on its own call, runs the handler -----------------------
    status, body = post(refund, "call-A")
    assert status == 200 and body["response"] == REFUND_OK, (status, body)
    assert runs == ["issue_refund"], runs

    # --- the other tool's token works for its own function, and only there --
    balance = tokens["get_balance"]
    del runs[:]
    status, body = post(balance, "call-A", "get_balance")
    assert status == 200 and body["response"] == BALANCE_OK, (status, body)
    assert runs == ["get_balance"], runs

    # --- every refusal, and none of them runs anything -----------------------
    del runs[:]
    for label, token, call_id, function in [
        ("another call", refund, "call-B", "issue_refund"),
        ("another function", refund, "call-A", "get_balance"),
        ("the other tool's token on this one", balance, "call-A", "issue_refund"),
        ("the other tool's token on another call", balance, "call-B", "get_balance"),
        ("altered", refund[:-4] + ("AAAA" if not refund.endswith("AAAA") else "BBBB"),
         "call-A", "issue_refund"),
    ]:
        status, body = post(token, call_id, function)
        assert status == 200 and SDK_REFUSAL in body["response"], (label, status, body)
        assert runs == [], (label, runs)

    # expired: mint with a window that has already closed
    sm = agent._session_manager
    sm.token_expiry_secs = -1
    expired = sm.create_tool_token("issue_refund", "call-A")
    sm.token_expiry_secs = 900
    status, body = post(expired, "call-A")
    assert status == 200 and SDK_REFUSAL in body["response"], (status, body)
    assert runs == [], runs

    # --- the gap the recipe closes: no token at all ---------------------------
    # The SDK checks a token only when one is present. The agent's own
    # middleware refuses the request before any handler.
    for token in (None, ""):  # absent, and present but empty
        status, body = post(token, "call-A")
        assert status == 403, (repr(token), status, body)
        assert body == {"response": "A per-call token is required."}, body
        assert runs == [], runs

    print(f"ok: {TOOLS} carry per-call tokens; the endpoint ran each handler "
          f"once for its own token and refused another call, another function, "
          f"an altered token, an expired token, no token and an empty token, "
          f"running nothing")


if __name__ == "__main__":
    main()
