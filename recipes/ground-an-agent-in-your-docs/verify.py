"""Prove the claim without a network.

Claim: a Datasphere tool searches only the selected tagged corpus and returns
the matching passages to the agent.

Proof: swap the REST client's HTTP layer for a recorder; run the tool as the
platform would; assert one POST to the documented Datasphere search path whose
body is a documented, required-complete search request carrying exactly the
corpus tags; assert the tool's response text is the returned passages and
nothing else; assert an empty result says so.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({"SIGNALWIRE_PROJECT_ID": "proj-1234", "SIGNALWIRE_API_TOKEN": "PT-test",
                   "SIGNALWIRE_SPACE": "example.signalwire.com", "DATASPHERE_TAGS": "product-docs,faq"})

import verifylib as V  # noqa: E402


def main():
    V.sdk_banner()
    from signalwire.rest import RestClient
    from app import DocsAgent
    client = RestClient()
    rec = V.record_everything(client, V.Recorder(responses=[
        {"chunks": [{"text": "Refunds are issued within 5 business days."},
                    {"text": "Contact billing to request a refund."}]},
        {"chunks": []},
    ]))
    agent = DocsAgent(client=client)

    r = agent._execute_swaig_function("search_docs", {"query": "how long do refunds take"}, call_id="c1")
    (call,) = rec.calls
    assert call["method"] == "POST" and call["path"] == "/api/datasphere/documents/search", call
    V.assert_documented("rest", "POST", call["path"], body=call["body"])
    assert call["body"]["tags"] == ["product-docs", "faq"], call["body"]
    assert call["body"]["query_string"] == "how long do refunds take"
    assert call["body"]["count"] == 3
    assert "Refunds are issued within 5 business days." in r["response"], r
    assert "action" not in r

    r = agent._execute_swaig_function("search_docs", {"query": "quantum widgets"}, call_id="c1")
    assert r["response"].startswith("No relevant documentation"), r

    doc = json.loads(agent._render_swml())
    ai = next(v for v in doc["sections"]["main"] if "ai" in v)["ai"]
    assert [f["function"] for f in ai["SWAIG"]["functions"]] == ["search_docs"]
    print("ok: POST /api/datasphere/documents/search with tags=['product-docs','faq']; passages -> response; empty -> 'not covered'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
