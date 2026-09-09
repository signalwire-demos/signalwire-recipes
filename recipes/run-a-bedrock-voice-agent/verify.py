"""Prove the claim without a network.

Claim: swapping `AgentBase` for `BedrockAgent` renders `amazon_bedrock`
instead of `ai`, with the prompt carrying three Bedrock settings. The SWAIG
function renders with the same schema on both, and the handler you register on
each returns the same reply.

Proof: build the parts desk on both base classes and render each with the
same call id. The `ai` document carries an `ai` verb and the Bedrock document
an `amazon_bedrock` verb and no `ai`; both validate against the bundled schema.
The two `SWAIG.functions` lists are equal once each webhook URL's per-call
token is set aside, and each URL points at the agent's `/swaig/` path. The
Bedrock prompt equals the `ai` prompt plus `voice_id`, `temperature` and
`top_p`, with the voice the environment set. `check_stock` executed on each agent returns the same exact reply,
for a stocked part, an out-of-stock part and an unknown one. Expected values
live here, not in app.py.
"""
import json
import os
import pathlib
import sys
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("SWML_BASIC_AUTH_USER", "signalwire")
os.environ.setdefault("SWML_BASIC_AUTH_PASSWORD", "verify-only-password")
os.environ["BEDROCK_VOICE_ID"] = "tiffany"   # not app.py's default, so the env must reach it
os.environ["AGENT_KIND"] = "ai"              # the module-level agent renders ai when asked to

import verifylib as V  # noqa: E402

CALL = "c1"
REPLIES = {"brake pads": "12 brake pads in stock.",
           "tubes": "tubes are out of stock. A restock lands Thursday.",
           "saddle": "We do not carry saddle."}


def verb(doc, name):
    return next(v for v in doc["sections"]["main"] if name in v)[name]


def main():
    V.sdk_banner()
    import app as recipe

    standard = recipe.build("ai")
    bedrock = recipe.build("bedrock")
    for a in (standard, bedrock):
        V.assert_basic_auth_from_env(a)
    ai_doc = json.loads(standard._render_swml(call_id=CALL))
    br_doc = json.loads(bedrock._render_swml(call_id=CALL))
    V.validate_swml(ai_doc)
    V.validate_swml(br_doc)

    # the top-level verb name changes
    assert V.verb_names(ai_doc) == ["answer", "ai"], V.verb_names(ai_doc)
    assert V.verb_names(br_doc) == ["answer", "amazon_bedrock"], V.verb_names(br_doc)
    ai, br = verb(ai_doc, "ai"), verb(br_doc, "amazon_bedrock")

    # same tools, same schemas. The two agents are two renders, so each
    # web_hook_url carries its own __token; the comparison strips that one
    # query value and nothing else, and asserts both carried one. Comparing the
    # raw lists would fail on the token alone and prove nothing about the schema.
    def without_token(functions):
        out = []
        for f in functions:
            f = dict(f)
            parts = urlsplit(f["web_hook_url"])
            query = [(k, v) for k, v in parse_qsl(parts.query) if k != "__token"]
            f["web_hook_url"] = urlunsplit(parts._replace(query=urlencode(query)))
            out.append(f)
        return out

    assert without_token(ai["SWAIG"]["functions"]) == without_token(br["SWAIG"]["functions"]), \
        (ai["SWAIG"], br["SWAIG"])
    for fns in (ai["SWAIG"]["functions"], br["SWAIG"]["functions"]):
        url = urlsplit(fns[0]["web_hook_url"])
        assert url.path == "/parts/swaig/", url.path
        assert "__token" in dict(parse_qsl(url.query)), "the SDK's secure default is kept"
    (fn,) = ai["SWAIG"]["functions"]
    assert fn["function"] == "check_stock", fn
    assert fn["parameters"]["required"] == ["part"], fn["parameters"]
    assert fn["parameters"]["properties"]["part"]["type"] == "string", fn["parameters"]
    assert "in stock" in fn["description"], fn["description"]

    # the prompt is the same text; Bedrock adds its voice and inference settings
    extra = {"voice_id", "temperature", "top_p"}
    assert set(br["prompt"]) == set(ai["prompt"]) | extra, (sorted(br["prompt"]), sorted(ai["prompt"]))
    assert {k: br["prompt"][k] for k in extra} == {"voice_id": "tiffany", "temperature": 0.7,
                                                  "top_p": 0.9}, br["prompt"]
    for key in ai["prompt"]:
        assert ai["prompt"][key] == br["prompt"][key], (key, ai["prompt"][key], br["prompt"][key])
    assert "parts desk" in json.dumps(ai["prompt"]["pom"]), ai["prompt"]

    # the same handler runs on both
    for part, reply in REPLIES.items():
        for a in (standard, bedrock):
            got = a._execute_swaig_function("check_stock", {"part": part}, call_id=CALL)
            assert got == {"response": reply}, (type(a).__name__, part, got)

    # the schema knows the verb this agent emits
    assert "AmazonBedrock" in V.swml_schema()["$defs"]

    # the environment picks the kind the module serves, and a bad kind stops
    module_doc = json.loads(recipe.agent._render_swml(call_id=CALL))
    assert V.verb_names(module_doc) == ["answer", "ai"], "AGENT_KIND=ai was not honoured"
    try:
        recipe.build("claude")
    except SystemExit as e:
        assert "ai or bedrock" in str(e), str(e)
    else:
        raise AssertionError("an unknown AGENT_KIND was accepted")

    print(f"ok: the same parts desk renders ai on AgentBase and amazon_bedrock on BedrockAgent "
          f"with identical SWAIG.functions; check_stock answers {REPLIES['brake pads']!r} on both")


if __name__ == "__main__":
    main()
