"""Prove the claim without a network.

Claim: an inbound fax on a number is received to a URL and your webhook is told
when it lands.

Proof: both surfaces validate against the SWML schema and consist of answer ->
receive_fax(status_url) -> hangup; the status webhook stores pages and the
document URL only for a successful receive.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.setdefault("PUBLIC_URL", "https://recipes.example.test")

import verifylib as V  # noqa: E402


def check(doc, label):
    V.validate_swml(doc)
    assert V.verb_names(doc) == ["answer", "receive_fax", "hangup"], (label, V.verb_names(doc))
    assert V.first(doc, "receive_fax")["status_url"].endswith("/fax-received"), label


def main():
    V.sdk_banner()
    import app as recipe
    check(recipe.build().get_document(), "python")
    check(V.load_yaml(HERE / "swml" / "agent.yaml"), "yaml")

    c = recipe.app.test_client()
    assert V.verb_names(c.get("/fax").get_json())[1] == "receive_fax"
    c.post("/fax-received", json={"call_id": "c1", "params": {"success": False, "result_text": "no carrier"}})
    assert recipe.received == {}
    c.post("/fax-received", json={"call_id": "c2", "from": "+15552223333",
                                  "params": {"success": True, "pages": 2, "document": "https://files.example.test/fax.pdf"}})
    assert recipe.received["c2"] == {"pages": 2, "document": "https://files.example.test/fax.pdf", "from": "+15552223333"}
    print("ok: answer -> receive_fax(status_url) -> hangup; document stored only on success")
    return 0


if __name__ == "__main__":
    sys.exit(main())
