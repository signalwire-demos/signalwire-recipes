"""Prove the claim without a network.

Claim: `calling.refer` transfers a SIP call via SIP REFER. It requires a
`device`, whose `type` is the enum's only value and whose `params` require a
`sip:` URI in `to`. Credentials and a `from` URI are optional, and a
`status_url` receives the lifecycle webhooks.

Proof: with the HTTP layer replaced by a recorder, each call adds exactly one
POST to the documented calling path and the body equals the expected shape. A
`to` or `from` that is not a `sip:` URI is refused before any request. The
required lists, the one-value device enum, the URI rules and the command
table's own sentence are read from the vendored spec. The TypeScript surface
goes through the same recorder seam and is held to the same expected bodies.
Expected values live here, not in app.py.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
USERNAME, PASSWORD = "pbx-user", "pbx-secret"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "SIP_REFER_USERNAME": USERNAME,
    "SIP_REFER_PASSWORD": PASSWORD,
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"
CALL = "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f"
TO = "sip:desk-2@pbx.example.com"
FROM = "sip:queue@pbx.example.com"
STATUS = "https://pbx.example.com/refer-events"
TABLE_ROW = "Transfer a SIP call via SIP REFER"


def spec_bits():
    """The refer variant, its device schema and the command table row."""
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for v in schemas["Calling.CallRequest"]["oneOf"]:
        cmd = deref(v["properties"]["command"])
        if "calling.refer" in (cmd.get("enum") or []):
            params = deref(v["properties"]["params"])
            props = {k: deref(x) for k, x in params["properties"].items()}
            table = spec["paths"][PATH]["post"]["description"]
            rows = dict(
                (cells[1].strip().strip("`"), cells[2].strip())
                for line in table.splitlines() if line.startswith("|")
                for cells in [line.split("|")] if len(cells) > 3)
            return v.get("required", []), params.get("required", []), props, deref, rows
    raise AssertionError("calling.refer is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # anything that is not a sip: URI never reaches the wire
    for args, field in [((CALL, "tel:+14155550123"), "to"),
                        ((CALL, TO, "sips:queue@pbx.example.com"), "from")]:
        try:
            recipe.refer(*args)
        except ValueError as exc:
            assert f"{field} must be a sip: URI" in str(exc), exc
        else:
            raise AssertionError(f"refer accepted a bad {field}")
    assert rec.calls == [], rec.calls

    recipe.refer(CALL, TO, FROM, STATUS)
    recipe.refer(CALL, TO)
    assert len(rec.calls) == 2, rec.calls

    top, required, props, deref, rows = spec_bits()
    assert set(top) == {"command", "id", "params"}, top
    assert required == ["device"], required
    assert rows.get("calling.refer") == TABLE_ROW, rows.get("calling.refer")

    device = props["device"]
    assert set(device["required"]) == {"type", "params"}, device["required"]
    kinds = deref(device["properties"]["type"])["enum"]
    assert kinds == ["sip"], kinds
    assert recipe.DEVICE_TYPE in kinds, recipe.DEVICE_TYPE

    sip = deref(device["properties"]["params"])
    assert sip["required"] == ["to"], sip["required"]
    to_rule = " ".join(deref(sip["properties"]["to"])["description"].split())
    assert "must start with `sip:`" in to_rule, to_rule
    from_rule = " ".join(deref(sip["properties"]["from"])["description"].split())
    assert "must start with `sip:` when provided" in from_rule, from_rule
    assert {"username", "password"} <= set(sip["properties"]), sorted(sip["properties"])
    assert "status_url" in props, sorted(props)

    expected = [
        {"command": "calling.refer", "id": CALL,
         "params": {"device": {"type": "sip",
                               "params": {"to": TO, "from": FROM,
                                          "username": USERNAME,
                                          "password": PASSWORD}},
                    "status_url": STATUS}},
        # no from and no status_url means neither key
        {"command": "calling.refer", "id": CALL,
         "params": {"device": {"type": "sip",
                               "params": {"to": TO, "username": USERNAME,
                                          "password": PASSWORD}}}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented refer params: {sorted(unknown)}"
        unknown = set(want["params"]["device"]["params"]) - set(sip["properties"])
        assert not unknown, f"undocumented sip params: {sorted(unknown)}"

    # the TypeScript surface, held to the same bodies
    node = V.node_surface(HERE, CALL, TO, FROM, STATUS,
                          env={"SIP_REFER_USERNAME": USERNAME,
                               "SIP_REFER_PASSWORD": PASSWORD})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert len(node["refused"]) == 2, node["refused"]
        assert "to must be a sip: URI" in node["refused"][0], node["refused"]
        assert "from must be a sip: URI" in node["refused"][1], node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 2, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        ts_note = "typescript sends the same two bodies and refuses the same URIs"

    print(f"ok: two POST {PATH} for id {CALL[:8]}...: calling.refer with a device of "
          f"the enum's only type and a sip: destination, with and without an "
          f"optional from and status_url; the spec's command table calls it "
          f"\"{TABLE_ROW}\"; a tel: destination is refused before any request; "
          f"{ts_note}")


if __name__ == "__main__":
    main()
