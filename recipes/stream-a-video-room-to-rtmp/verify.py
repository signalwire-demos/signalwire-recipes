"""Prove the claim without a network.

Claim: one POST to a room's streams path with a `url` asks the platform to
stream the room's session to an RTMP or RTMPS server of yours. The stream id
in the response is the handle: a PUT to the stream's path carries a new `url`,
and a DELETE by id answers 204.

Proof: the HTTP layer is a recorder that answers the stream create with an
id. The four helpers make four requests in order. They POST the stream with
exactly `{"url": ...}`, PUT the new URL by stream id, DELETE by stream id, and
GET the room's streams. The vendored REST spec documents each path and body
and requires exactly `url` on the create and the update. It carries the stream
`id` in the create response, answers the delete with 204, and documents the
same `url` field on the conference streams path. Expected values live here,
not in app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "RTMP_URL": "rtmps://live.example.com/app/stream-key",
})

import verifylib as V  # noqa: E402

ROOMS = "/api/video/rooms"
RID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
SID = "2b1a4f60-0d8e-4c3b-9a7f-5e6d7c8b9a01"
URL = "rtmps://live.example.com/app/stream-key"
URL2 = "rtmp://backup.example.com/app/stream-key"


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def body_schema(spec, path, method):
    op = spec["paths"][path][method]
    return deref(spec, op["requestBody"]["content"]["application/json"]["schema"])


def response_props(spec, path, method):
    op = spec["paths"][path][method]
    code = next(c for c in op["responses"] if c.startswith("2"))
    content = op["responses"][code].get("content", {})
    if not content:
        return code, {}
    schema = deref(spec, content["application/json"]["schema"])
    return code, schema.get("properties", {})


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[{"id": SID, "url": URL, "stream_type": "rtmp"},
                                {"id": SID, "url": URL2, "stream_type": "rtmp"},
                                {}, {"data": [{"id": SID, "url": URL2}]}])
    recipe.client.video.rooms._http = rec
    recipe.client.video.streams._http = rec

    stream = recipe.start_stream(RID)
    recipe.move_stream(stream["id"], URL2)
    recipe.stop_stream(stream["id"])
    recipe.streams(RID)

    expected = [("POST", f"{ROOMS}/{RID}/streams"), ("PUT", f"/api/video/streams/{SID}"),
                ("DELETE", f"/api/video/streams/{SID}"), ("GET", f"{ROOMS}/{RID}/streams")]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    start, move, stop, listing = rec.calls

    # exact bodies, then the spec's word on each
    assert start["body"] == {"url": URL}, start
    assert move["body"] == {"url": URL2}, move
    assert stop["body"] is None and listing["body"] is None, (stop, listing)
    assert listing["params"] is None, listing

    spec = V.spec("rest")
    V.assert_documented("rest", "POST", f"{ROOMS}/{{id}}/streams", start["body"])
    V.assert_documented("rest", "PUT", "/api/video/streams/{id}", move["body"])
    V.assert_documented("rest", "DELETE", "/api/video/streams/{id}", None)
    V.assert_documented("rest", "GET", f"{ROOMS}/{{id}}/streams", None)
    assert body_schema(spec, f"{ROOMS}/{{id}}/streams", "post")["required"] == ["url"]
    assert body_schema(spec, "/api/video/streams/{id}", "put")["required"] == ["url"]
    url_desc = deref(spec, body_schema(spec, f"{ROOMS}/{{id}}/streams", "post")
                     ["properties"]["url"])["description"]
    assert "RTMP or RTMPS URL" in url_desc, url_desc
    assert spec["paths"]["/api/video/streams/{id}"]["put"]["summary"] == "Update stream"
    assert spec["paths"]["/api/video/streams/{id}"]["delete"]["summary"] == "Delete stream"

    # the id the create returns is what the other two paths take
    code, props = response_props(spec, f"{ROOMS}/{{id}}/streams", "post")
    assert code == "201" and {"id", "url", "stream_type"} <= set(props), (code, sorted(props))
    delete = spec["paths"]["/api/video/streams/{id}"]["delete"]["responses"]
    assert "204" in delete and "no content to send" in delete["204"]["description"], delete.get("204")
    assert set(body_schema(spec, "/api/video/streams/{id}", "put")["properties"]) == {"url"}

    # the same field on a conference, as the README says
    conf = body_schema(spec, "/api/video/conferences/{id}/streams", "post")
    assert conf["required"] == ["url"], conf["required"]

    # an unset RTMP_URL stops start_stream before any request
    recipe.RTMP_URL = None
    try:
        recipe.start_stream(RID)
    except SystemExit as e:
        assert "RTMP_URL" in str(e), str(e)
    else:
        raise AssertionError("start_stream without a URL did not stop")
    assert len(rec.calls) == 4, rec.calls

    print(f"ok: POST {ROOMS}/{RID[:8]}.../streams url={URL}, PUT and DELETE "
          f"/api/video/streams/{SID[:8]}..., GET the room's streams; the spec requires exactly "
          f"url on create and update")


if __name__ == "__main__":
    main()
