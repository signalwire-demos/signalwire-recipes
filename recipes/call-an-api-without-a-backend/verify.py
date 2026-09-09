"""Prove the claim without a network.

Claim: a DataMap tool calls a third-party API from SignalWire's side and
templates the response, so no service of yours is in the tool path.

Proof: the rendered SWML carries the request, the response template and the
failure path inside the function definition, and the function has no `url` of
yours for the platform to call back to. The SDK refuses to run it locally,
which is the claim stated from the other side.
"""
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


def tool_of(doc, label):
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    fn = next(f for f in ai["SWAIG"]["functions"]
              if f["function"] == "look_up_book")
    assert "data_map" in fn, (label, fn)
    return fn


def main():
    V.sdk_banner()
    from app import CatalogueAgent

    agent = CatalogueAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    fn = tool_of(doc, "python")

    # No tool callback: a normal SWAIG function carries web_hook_url for the
    # platform to POST to. This one carries a data_map instead, so nothing of
    # ours is called when the model uses it. ("url" is not the key a callback
    # would arrive under, so asserting its absence proves nothing.)
    assert "data_map" in fn, fn
    assert "web_hook_url" not in fn, fn
    dm = fn["data_map"]

    # The request the platform will make, with the argument templated in.
    (hook,) = dm["webhooks"]
    assert hook["method"] == "GET", hook
    assert hook["url"] == "https://openlibrary.org/isbn/${args.isbn}.json", hook

    # Assert the keys the platform receives, not the SDK methods that built
    # them: .output() lands inside the webhook, .fallback_output() at the top.
    assert "${response.title}" in hook["output"]["response"], hook
    assert hook["error_keys"] == ["error"], hook
    assert "could not reach" in dm["output"]["response"], dm["output"]
    assert "${response." not in dm["output"]["response"], dm["output"]

    # The parameter the model has to fill.
    params = fn["parameters"]
    assert params["required"] == ["isbn"], params
    assert params["properties"]["isbn"]["description"], params

    # The SDK will not execute it here, because SignalWire executes it there.
    r = agent._execute_swaig_function("look_up_book", {"isbn": "9780571225385"},
                                      call_id="c1")
    assert "should be executed by SignalWire server" in r["response"], r

    # The hand-written surface is the same artifact, not a paraphrase of it.
    yaml_fn = tool_of(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")
    ydm = yaml_fn["data_map"]
    assert ydm["webhooks"][0]["url"] == hook["url"], ydm
    assert ydm["webhooks"][0]["method"] == hook["method"], ydm
    assert ydm["webhooks"][0]["error_keys"] == hook["error_keys"], ydm
    assert yaml_fn["parameters"]["required"] == ["isbn"], yaml_fn
    for template in ("${args.isbn}", "${response.title}"):
        assert template in ydm["webhooks"][0]["output"]["response"], ydm

    print(f"ok: look_up_book carries {hook['method']} {hook['url']} with a "
          f"${{response.*}} template and a fallback; no url of ours, and local "
          f"execution is refused")


if __name__ == "__main__":
    main()
