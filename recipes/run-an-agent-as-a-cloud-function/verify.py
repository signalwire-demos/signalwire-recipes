"""Prove the claim without a network.

Claim: the same agent file runs as an AWS Lambda handler. `agent.run(event,
context)` returns the SWML for a request to the root and the tool result for a
POST to `/swaig`. Both sit behind the same basic auth, in the response shape
API Gateway expects.

Proof: call `handler` with Lambda events in the HTTP API payload shape, forcing
Lambda mode through `AWS_LAMBDA_FUNCTION_NAME` so nothing depends on the
machine. A root request with the right `Authorization` header returns
statusCode 200 and a body that parses and validates as SWML with the one tool,
whose webhook URL starts with the `SWML_PROXY_URL_BASE` a deployment must set.
A `/swaig` POST whose body is the platform's tool payload returns 200 and the
handler's exact result. A request with no header, or the wrong password, gets
the SDK's 401 challenge. Expected values live here, not in app.py.
"""
import base64
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
# what the Lambda runtime sets; it is what run() keys its mode on
os.environ["AWS_LAMBDA_FUNCTION_NAME"] = "stock-agent"
# what your deployment must set: the public base the webhook URLs render from
BASE = "https://abc123.execute-api.us-east-1.amazonaws.com"
os.environ["SWML_PROXY_URL_BASE"] = BASE

IN_STOCK = "14 of SK-2210 in stock."


def auth(password=None):
    raw = f"{os.environ['SWML_BASIC_AUTH_USER']}:{password or os.environ['SWML_BASIC_AUTH_PASSWORD']}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


def event(path="/", method="GET", body=None, headers=None):
    """An API Gateway HTTP API (payload v2) event, the shape run() reads."""
    e = {"version": "2.0", "rawPath": path, "rawQueryString": "",
         "headers": {"content-type": "application/json", **(headers or {})},
         "requestContext": {"http": {"method": method, "path": path}},
         "isBase64Encoded": False}
    if body is not None:
        e["body"] = json.dumps(body)
    return e


def main():
    V.sdk_banner()
    import app as recipe

    V.assert_basic_auth_from_env(recipe.agent)

    # the document, as API Gateway would hand it back
    r = recipe.handler(event(headers={"authorization": auth()}), None)
    assert r["statusCode"] == 200, r
    assert r["headers"]["Content-Type"] == "application/json", r["headers"]
    doc = json.loads(r["body"])
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    (fn,) = ai["SWAIG"]["functions"]
    assert fn["function"] == "check_stock", fn["function"]
    # the tool's webhook points back through API Gateway, not at a host the
    # function does not have. In serverless mode the SDK drops the agent's
    # route and renders <base>/swaig/, with the basic-auth pair in the URL.
    from urllib.parse import urlsplit
    hook = urlsplit(fn["web_hook_url"])
    assert (hook.scheme, hook.hostname, hook.path) == ("https", urlsplit(BASE).hostname, "/swaig/"), \
        (hook.scheme, hook.hostname, hook.path)
    assert hook.username == "signalwire" and "__token=" in hook.query, "credentials and token"

    # the tool, from the platform's POST body
    body = {"function": "check_stock", "call_id": "c1",
            "argument": {"parsed": [{"sku": "sk-2210"}], "raw": "{\"sku\": \"sk-2210\"}"}}
    r = recipe.handler(event("/swaig", "POST", body, {"authorization": auth()}), None)
    assert r["statusCode"] == 200, r
    assert json.loads(r["body"]) == {"response": IN_STOCK}, r["body"]

    # basic auth is still the gate: no header, or the wrong password
    for headers in ({}, {"authorization": auth("wrong")}):
        r = recipe.handler(event("/swaig", "POST", body, headers), None)
        assert r["statusCode"] == 401, r
        assert "WWW-Authenticate" in r["headers"], r["headers"]

    print(f"ok: in Lambda mode, GET / returns 200 with valid SWML for ['check_stock'], "
          f"POST /swaig returns 200 with {IN_STOCK!r}, and a missing or wrong "
          f"Authorization gets the 401 challenge")


if __name__ == "__main__":
    main()
