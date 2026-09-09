"""Prove the claim without a network.

Claim: `calling.stream` opens an authenticated WebSocket for a live call's
audio. The url must be `wss://`, the track is one of the spec's three, the
bearer token travels as a param, and custom parameters ride along as metadata.
`calling.stream.stop` ends it by control id.

Proof: with the HTTP layer replaced by a recorder, each helper adds exactly one
POST to the documented calling path and the body equals the expected shape. A
`ws://` url and an unknown track are refused before any request. The required
lists, the track enum, the TLS rule and the bearer-token behaviour are read from
the vendored spec's own text. The TypeScript surface goes through the same
recorder seam and is held to the same expected bodies. Expected values live
here, not in app.py.
"""
import json
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
TOKEN = "stream-secret"
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "STREAM_BEARER_TOKEN": TOKEN,
})

import verifylib as V  # noqa: E402

PATH = "/api/calling/calls"
CALL = "6d3f4a0e-2b1c-4e7a-9f0d-1c2b3a4d5e6f"
CONTROL = "support-audio"
URL = "wss://media.example.com/calls"
STATUS = "https://media.example.com/stream-events"
TAG = "ticket-4417"
TRACKS = ["inbound_track", "outbound_track", "both_tracks"]


def variant(command):
    """Description, required lists and params properties, from the spec."""
    spec = V.spec("rest")
    schemas = spec["components"]["schemas"]

    def deref(node):
        while isinstance(node, dict) and "$ref" in node:
            node = schemas[node["$ref"].split("/")[-1]]
        return node

    for v in schemas["Calling.CallRequest"]["oneOf"]:
        cmd = deref(v["properties"]["command"])
        if command in (cmd.get("enum") or []):
            params = deref(v["properties"]["params"])
            props = {k: deref(x) for k, x in params.get("properties", {}).items()}
            return (" ".join(v.get("description", "").split()),
                    params.get("required", []), props)
    raise AssertionError(f"{command} is not a documented call command")


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder()
    recipe.client.calling._http = rec

    # plain ws:// and an unknown track never reach the wire
    refusals = [(("ws://media.example.com/calls",), "wss://"),
                ((URL, "left_track"), "track must be one of")]
    for args, expected_message in refusals:
        try:
            recipe.start(CALL, *args)
        except ValueError as exc:
            assert expected_message in str(exc), exc
        else:
            raise AssertionError(f"start accepted {args}")
    assert rec.calls == [], rec.calls

    recipe.start(CALL, URL, status_url=STATUS, tag=TAG)
    recipe.start(CALL, URL)
    recipe.stop(CALL)
    assert len(rec.calls) == 3, rec.calls

    desc, required, props = variant("calling.stream")
    assert set(required) == {"control_id", "url"}, required
    assert "Audio is sent to a `wss://` URL" in desc, desc
    assert "`custom_parameters` pass through to the endpoint" in desc, desc
    tls = " ".join(props["url"]["description"].split())
    assert "Must start with `wss://`" in tls, tls
    assert "plain `ws://` is rejected" in tls, tls
    assert props["track"]["enum"] == TRACKS, props["track"]
    assert list(recipe.TRACKS) == TRACKS, recipe.TRACKS
    bearer = " ".join(props["authorization_bearer_token"]["description"].split())
    assert "Authorization: Bearer <token>" in bearer, bearer
    assert props["status_url_method"]["enum"] == ["GET", "POST"], props["status_url_method"]

    desc, required, props = variant("calling.stream.stop")
    assert required == ["control_id"], required

    expected = [
        {"command": "calling.stream", "id": CALL,
         "params": {"control_id": CONTROL, "url": URL, "track": "both_tracks",
                    "codec": "PCMU", "name": "support",
                    "authorization_bearer_token": TOKEN,
                    "custom_parameters": {"tag": TAG},
                    "status_url": STATUS, "status_url_method": "POST"}},
        # no status_url and no tag means neither key, rather than a null
        {"command": "calling.stream", "id": CALL,
         "params": {"control_id": CONTROL, "url": URL, "track": "both_tracks",
                    "codec": "PCMU", "name": "support",
                    "authorization_bearer_token": TOKEN}},
        {"command": "calling.stream.stop", "id": CALL,
         "params": {"control_id": CONTROL}},
    ]
    for call, want in zip(rec.calls, expected):
        assert (call["method"], call["path"]) == ("POST", PATH), call
        V.assert_documented("rest", "POST", PATH, None)
        assert call["body"] == want, json.dumps(call["body"], indent=1)
        _, _, props = variant(want["command"])
        unknown = set(want["params"]) - set(props)
        assert not unknown, f"undocumented {want['command']} params: {sorted(unknown)}"

    # the TypeScript surface, held to the same bodies
    node = V.node_surface(HERE, CALL, URL, STATUS, TAG, env={"STREAM_BEARER_TOKEN": TOKEN})
    if node is None:
        ts_note = "typescript not run (npm ci in typescript/ first)"
    else:
        assert len(node["refused"]) == 2, node["refused"]
        assert "wss://" in node["refused"][0], node["refused"]
        assert "track must be one of" in node["refused"][1], node["refused"]
        assert [(c["method"], c["path"]) for c in node["captured"]] == [
            ("POST", PATH)] * 3, node["captured"]
        assert [c["body"] for c in node["captured"]] == expected, node["captured"]
        ts_note = "typescript sends the same three bodies and refuses ws:// too"

    print(f"ok: three POST {PATH} for id {CALL[:8]}...: calling.stream to {URL} on "
          f"track both_tracks with a bearer token, custom parameters and a POST "
          f"status_url, the same without the optional keys, then "
          f"calling.stream.stop on control_id {CONTROL}; a ws:// url and an "
          f"unknown track are refused before any request; {ts_note}")


if __name__ == "__main__":
    main()
