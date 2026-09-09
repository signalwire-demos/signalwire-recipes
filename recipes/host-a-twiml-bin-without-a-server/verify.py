"""Prove the claim without a network.

Claim: a cXML document is hosted by SignalWire from one POST, whose response
carries the URL it is served from, and one more POST puts a number on it. No
server of yours is in the call path.

Proof: with the HTTP layer replaced by a recorder, the create is a documented
POST to `cxml_scripts` whose body is exactly `display_name` and `contents`, and
the contents are the document this verifier expects, byte for byte. The helper
returns the id and `request_url` the response carried. The number lookup is a
documented GET whose `filter_number` the spec describes as a contains match, so
the listing answers with a longer neighbour first and the recipe must still
pick the exact number; a listing without it raises and sends no bind. The bind
is a documented POST with a `handler` from the spec's enum. The compat twin,
`LamlBins`, requires `Name` and takes `Contents`. The TypeScript surface makes
the same requests and refuses the same absent number. Expected values live here.
"""
import os
import pathlib
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
# not either surface's default, so a surface that never read the environment
# would render a different document and fail
FORWARD = "+15557654321"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "FORWARD_TO": FORWARD,
})

import verifylib as V  # noqa: E402

SCRIPTS = "/api/fabric/resources/cxml_scripts"
NUMBERS = "/api/relay/rest/phone_numbers"
SCRIPT_ID, URL = "scr-abc", "https://example.signalwire.com/laml-bins/scr-abc"
MAIN, NID = "+15551230000", "pn-111"
NEAR, NEAR_ID = MAIN + "9", "pn-near"      # a contains match returns this too
NAME = "workshop line"
EXPECTED_XML = ('<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
                '  <Say>Connecting you to the workshop.</Say>\n'
                f'  <Dial timeout="20">{FORWARD}</Dial>\n</Response>\n')
BIND = f"/api/fabric/resources/{SCRIPT_ID}/phone_routes"
EXPECTED = [
    ("POST", SCRIPTS, {"display_name": NAME, "contents": EXPECTED_XML}),
    ("GET", NUMBERS, None),
    ("POST", BIND, {"phone_route_id": NID, "handler": "calling"}),
]
LISTING = {"data": [{"id": NEAR_ID, "number": NEAR}, {"id": NID, "number": MAIN}]}


def check_xml(text):
    """The expected document is well-formed cXML of the shape the README shows."""
    root = ET.fromstring(text)
    assert root.tag == "Response", root.tag
    assert [c.tag for c in root] == ["Say", "Dial"], [c.tag for c in root]
    say, dial = root
    assert say.text == "Connecting you to the workshop.", say.text
    assert dial.text == FORWARD and dial.get("timeout") == "20", (dial.text, dial.attrib)


def main():
    V.sdk_banner()
    import app as recipe

    check_xml(EXPECTED_XML)

    rec = V.Recorder(responses=[
        {"id": SCRIPT_ID, "type": "cxml_script", "cxml_script": {"request_url": URL}},
        LISTING,
        {},
    ])
    V.record_everything(recipe.client, rec)
    assert recipe.create() == (SCRIPT_ID, URL)
    recipe.point_number(SCRIPT_ID, MAIN)

    got = [(c["method"], c["path"], c["body"]) for c in rec.calls]
    assert got == EXPECTED, got
    create, listing, bind = rec.calls
    V.assert_documented("rest", "POST", SCRIPTS, create["body"])
    assert listing["params"] == {"filter_number": MAIN}, listing
    V.assert_documented("rest", "GET", NUMBERS, None, listing["params"])
    V.assert_documented("rest", "POST", bind["path"], bind["body"])
    schemas = V.spec("rest")["components"]["schemas"]
    handler = schemas["PhoneRouteAssignRequest"]["properties"]["handler"]
    assert bind["body"]["handler"] in schemas[handler["$ref"].split("/")[-1]]["enum"]

    # a number the project does not hold: nothing is bound
    rec2 = V.Recorder(responses=[{"data": [{"id": NEAR_ID, "number": NEAR}]}])
    V.record_everything(recipe.client, rec2)
    try:
        recipe.point_number(SCRIPT_ID, MAIN)
    except LookupError as e:
        assert MAIN in str(e), e
    else:
        raise AssertionError("a number the project does not hold was bound")
    assert [c["method"] for c in rec2.calls] == ["GET"], rec2.calls

    # the spec: the create needs exactly these two fields, the response carries
    # the URL the platform serves the script from, and the filter is a contains
    # match, which is why the exact comparison above matters
    req = schemas["CXMLScriptCreateRequest"]
    assert sorted(req["required"]) == ["contents", "display_name"], req["required"]
    resp = schemas["CXMLScriptResponse"]["properties"]["cxml_script"]
    while "$ref" in resp:
        resp = schemas[resp["$ref"].split("/")[-1]]
    assert "request_url" in resp["properties"], sorted(resp["properties"])
    spec = V.spec("rest")
    query = spec["paths"][NUMBERS]["get"]["parameters"]
    filter_doc = next(p for p in query if p["name"] == "filter_number")["description"]
    assert "containing this value" in filter_doc, filter_doc
    # updating the script is a documented PUT of new contents
    update = f"{SCRIPTS}/{SCRIPT_ID}"
    V.assert_documented("rest", "PUT", update, {"contents": EXPECTED_XML})
    # the compat twin
    compat = V.spec("compat")
    laml = [p for p in compat["paths"] if p.endswith("/LamlBins")]
    assert laml, "no LamlBins path in the compat spec"
    body = list(compat["paths"][laml[0]]["post"]["requestBody"]["content"].values())[0]
    body = body["schema"]
    while "$ref" in body:
        body = compat["components"]["schemas"][body["$ref"].split("/")[-1]]
    assert body["required"] == ["Name"] and "Contents" in body["properties"], body

    node = V.node_surface(HERE, SCRIPT_ID, URL, MAIN, NID, NEAR, NEAR_ID)
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        tgot = [(c["method"], c["path"], c["body"]) for c in node["captured"]]
        assert tgot == EXPECTED, tgot
        query = f"?filter_number={MAIN.replace('+', '%2B')}"
        assert node["captured"][1]["query"] == query, node["captured"][1]
        assert node["created"] == [SCRIPT_ID, URL], node["created"]
        assert node["absent"]["refused"] is True, node["absent"]
        assert node["absent"]["methods"] == ["GET"], node["absent"]
        ts_note = ("typescript makes the same three requests, picks the exact number "
                   "past the neighbour, and binds nothing for a number it cannot find")

    print(f"ok: POST {SCRIPTS} with display_name and a Say + Dial({FORWARD}) document, "
          f"the response's request_url {URL} comes back, then the exact number is "
          f"picked past a longer neighbour and bound with handler=calling; a number "
          f"the project lacks raises and binds nothing; the compat twin LamlBins needs "
          f"Name and takes Contents; {ts_note}")


if __name__ == "__main__":
    main()
