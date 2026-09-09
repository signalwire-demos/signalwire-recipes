"""Prove the claim without a network.

Claim: the rendered document carries a filler phrase and a wait file on the
slow tool, and a filler pool on each language entry, under the keys the
platform reads to fill the gap while a tool runs.

Proof: render the SWML twice, once with a hosted wait file and once without,
and assert the exact values of `fillers`, `wait_file`, `wait_file_loops`,
`function_fillers`, `speech_fillers` and `languages_enabled`. Expected values
live here, not in app.py, so swapping the English and Spanish pools fails. The
document must validate against the bundled schema, and a two-language
`fillers` dict must not, which is why per-language pools live on `languages`.
What a caller hears, and when, is platform behaviour the README cites.
"""
import copy
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
os.environ["LOOKUP_DELAY_SECONDS"] = "0"

# Expected values live here. A verifier that imported them from app.py would
# pass with both sides wrong.
HOSTED = "https://cdn.example.com/audio/hold.mp3"
EXPECT_FUNCTION_FILLER = {"en-US": ["Checking the warehouse now."]}
EXPECT_LANGUAGES = {
    "en-US": {"name": "English",
              "speech_fillers": ["Right.", "Okay."],
              "function_fillers": ["One moment while I check the shelf.",
                                   "Let me look that up for you."]},
    "es-ES": {"name": "Spanish",
              "speech_fillers": ["Vale.", "Claro."],
              "function_fillers": ["Un momento, estoy comprobando.",
                                   "Deme un segundo."]},
}


def render(wait_file_url):
    """Build a fresh agent under the given WAIT_FILE_URL and render it."""
    os.environ["WAIT_FILE_URL"] = wait_file_url
    import app
    importlib.reload(app)          # the module reads the variable at import
    agent = app.StockAgent()
    V.assert_basic_auth_from_env(agent)
    doc = json.loads(agent._render_swml())
    V.validate_swml(doc)
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    fn = next(f for f in ai["SWAIG"]["functions"] if f["function"] == "check_stock")
    return agent, doc, ai, fn


def main():
    V.sdk_banner()

    # --- with a hosted wait file --------------------------------------------
    agent, doc, ai, fn = render(HOSTED)
    assert fn["fillers"] == EXPECT_FUNCTION_FILLER, fn["fillers"]
    # an absolute URL passes through untouched; the SDK only rewrites
    # relative paths against its own base URL
    assert fn["wait_file"] == HOSTED, fn["wait_file"]
    assert fn["wait_file_loops"] == 3, fn

    assert ai["params"]["languages_enabled"] is True, ai.get("params")
    langs = {l["code"]: l for l in ai["languages"]}
    assert set(langs) == set(EXPECT_LANGUAGES), sorted(langs)
    for code, want in EXPECT_LANGUAGES.items():
        got = langs[code]
        assert got["name"] == want["name"], got
        assert got["speech_fillers"] == want["speech_fillers"], (code, got)
        assert got["function_fillers"] == want["function_fillers"], (code, got)
        # the deprecated single key is not what the platform reads
        assert "fillers" not in got, got

    # --- the shape the recipe deliberately avoids --------------------------
    bad = copy.deepcopy(doc)
    bad_fn = next(f for f in next(v for v in bad["sections"]["main"] if "ai" in v)
                  ["ai"]["SWAIG"]["functions"] if f["function"] == "check_stock")
    bad_fn["fillers"] = {"en-US": ["Checking."], "es-ES": ["Comprobando."]}
    try:
        V.validate_swml(bad)
    except AssertionError:
        pass
    else:
        raise AssertionError("a two-language fillers dict validated; the "
                             "schema has changed, revisit the recipe")

    # --- the tool still answers ---------------------------------------------
    r = agent._execute_swaig_function("check_stock", {"sku": "sk-2210"}, call_id="c1")
    assert r["response"] == "Part SK-2210: 14 in stock.", r
    r = agent._execute_swaig_function("check_stock", {"sku": "SK-2211"}, call_id="c1")
    assert r["response"] == "Part SK-2211 is out of stock.", r
    r = agent._execute_swaig_function("check_stock", {"sku": "SK-0000"}, call_id="c1")
    assert r["response"].startswith("NOT_FOUND: no part with SKU SK-0000"), r

    # --- without a wait file, no wait file is promised ---------------------
    _, _, _, fn2 = render("")
    assert "wait_file" not in fn2 and "wait_file_loops" not in fn2, fn2
    assert fn2["fillers"] == EXPECT_FUNCTION_FILLER, fn2

    # the trap the README warns about: one kind of filler alone writes the
    # deprecated single `fillers` key on the language entry
    from signalwire import AgentBase

    class OneKind(AgentBase):
        def __init__(self):
            super().__init__(name="one-kind", route="/one-kind")
            self.prompt_add_section("Role", "test")
            self.add_language("English", "en-US", "rime.spore",
                              speech_fillers=["Right."])

    one = json.loads(OneKind()._render_swml())
    lang = next(v for v in one["sections"]["main"] if "ai" in v)["ai"]["languages"][0]
    assert "fillers" in lang and "speech_fillers" not in lang, lang

    print(f"ok: check_stock carries fillers {fn['fillers']} and wait_file "
          f"looped x{fn['wait_file_loops']} when WAIT_FILE_URL is set, neither "
          f"key when it is not; {sorted(langs)} carry the exact pools; a "
          f"two-language function filler is refused by the schema")


if __name__ == "__main__":
    main()
