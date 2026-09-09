"""Prove the claim without a network.

Claim: a pass lists every call recording across pages, copies each one older
than your retention window to storage you control, and then deletes it from
SignalWire. Nothing is deleted that was not copied first.

Proof: the HTTP layer is a recorder that answers with two recording pages
joined by `links.next`: two recordings past the window, one inside it. The
media fetcher is a fake that records the URLs it was asked for, and the
recorder's DELETE checks that the file is complete on disk at that moment. The
pass makes GET, GET, DELETE, DELETE in that order, downloads exactly the two
expired URLs, writes each under its id, and leaves the fresh one alone. A
second pass whose fetcher raises makes no DELETE at all. The real `download`
sends basic auth to an https URL on the space and refuses anything else. Every
path is documented, the delete answers 204, and the spec's four recording
variants all carry `id`, `created_at` and `url`. Expected values live here,
not in app.py.
"""
import base64
import os
import pathlib
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
EXPORTS = pathlib.Path(tempfile.mkdtemp(prefix="recipe-exports-"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
    "RETENTION_DAYS": "30",
    "EXPORT_DIR": str(EXPORTS),
})

import verifylib as V  # noqa: E402

PATH = "/api/relay/rest/recordings"
NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)
NEXT = f"https://example.signalwire.com{PATH}?page_token=tok2"


def body_for(url):
    """What the fake fetcher returns for a URL, and therefore the byte_size the
    fixture must carry for the copy to count as complete."""
    return b"RIFF" + url.encode()


def recording(rid, created, ext="wav"):
    url = f"https://example.signalwire.com/api/relay/rest/recordings/{rid}.{ext}"
    return {"id": rid, "created_at": created, "status": "finished", "duration_in_seconds": 61,
            "url": url, "byte_size": len(body_for(url))}


OLD1 = recording("rec-old-1", "2026-07-01T09:00:00Z")          # 63 days old
FRESH = recording("rec-fresh", "2026-08-30T09:00:00Z")         # 3 days old
OLD2 = recording("rec-old-2", "2026-08-02T09:00:00Z", "mp3")   # 31 days old
PAGE1 = {"data": [OLD1, FRESH], "links": {"self": "...", "next": NEXT}}
PAGE2 = {"data": [OLD2], "links": {"self": "..."}}


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def main():
    V.sdk_banner()
    import app as recipe

    rec = V.Recorder(responses=[PAGE1, PAGE2, {}, {}])
    recipe.client.recordings._http = rec
    fetched = []
    events = []                                   # one stream: copies and deletes, in order

    def fake_fetch(url):
        fetched.append(url)
        events.append(("copy", url.rsplit("/", 1)[-1]))
        return body_for(url)

    real_delete = rec.delete

    def delete_checking_disk(path):
        rid = path.rsplit("/", 1)[-1]
        on_disk = list(EXPORTS.glob(f"{rid}.*"))
        assert len(on_disk) == 1, f"DELETE of {rid} before its copy landed: {on_disk}"
        # the whole body, at the moment of the delete, not a prefix afterwards
        url = next(u for u in fetched if u.rsplit("/", 1)[-1].startswith(rid))
        assert on_disk[0].read_bytes() == body_for(url), on_disk[0]
        events.append(("delete", rid))
        return real_delete(path)

    rec.delete = delete_checking_disk

    moved = recipe.export_and_delete(now=NOW, fetch=fake_fetch)

    expected = [("GET", PATH), ("GET", PATH), ("DELETE", f"{PATH}/rec-old-1"),
                ("DELETE", f"{PATH}/rec-old-2")]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]
    page1, page2 = rec.calls[:2]
    assert page1["params"] is None, page1
    assert page2["params"] == {"page_token": "tok2"}, page2
    assert fetched == [OLD1["url"], OLD2["url"]], fetched
    assert events == [("copy", "rec-old-1.wav"), ("delete", "rec-old-1"),
                      ("copy", "rec-old-2.mp3"), ("delete", "rec-old-2")], events
    assert [m["id"] for m in moved] == ["rec-old-1", "rec-old-2"], moved
    # the report is the whole record: id, when it was made, where the copy is
    assert moved == [
        {"id": "rec-old-1", "created_at": "2026-07-01T09:00:00Z", "path": str(EXPORTS / "rec-old-1.wav")},
        {"id": "rec-old-2", "created_at": "2026-08-02T09:00:00Z", "path": str(EXPORTS / "rec-old-2.mp3")},
    ], moved
    for m, ext in zip(moved, ("wav", "mp3")):
        path = pathlib.Path(m["path"])
        assert path == EXPORTS / f"{m['id']}.{ext}", path
        assert path.read_bytes() == b"RIFF" + f"https://example.signalwire.com{PATH}/{m['id']}.{ext}".encode()
    assert not (EXPORTS / "rec-fresh.wav").exists()

    # a short body is a truncated copy: nothing written, nothing deleted
    rec3 = V.Recorder(responses=[{"data": [OLD1], "links": {}}])
    recipe.client.recordings._http = rec3
    for f in EXPORTS.glob("rec-old-1.*"):
        f.unlink()
    try:
        recipe.export_and_delete(now=NOW, fetch=lambda url: body_for(url)[:-1])
    except ValueError as e:
        assert "nothing deleted" in str(e), e
    else:
        raise AssertionError("a short copy did not stop the pass")
    assert [c["method"] for c in rec3.calls] == ["GET"], rec3.calls
    assert not list(EXPORTS.glob("rec-old-1.*")), "a truncated copy must not be written"

    # RETENTION_DAYS below one is refused at startup, in a fresh interpreter
    import subprocess
    import signalwire
    env = dict(os.environ, RETENTION_DAYS="0",
               PYTHONPATH=os.path.dirname(os.path.dirname(signalwire.__file__)))
    proc = subprocess.run([sys.executable, "-c", "import app"], cwd=HERE / "python",
                          env=env, capture_output=True, text=True)
    assert proc.returncode != 0 and "RETENTION_DAYS must be at least 1" in proc.stderr, \
        (proc.returncode, proc.stderr[-300:])

    # a copy that fails stops the pass before the delete
    rec2 = V.Recorder(responses=[{"data": [OLD1], "links": {}}])
    recipe.client.recordings._http = rec2

    def broken_fetch(url):
        raise OSError("storage unreachable")

    try:
        recipe.export_and_delete(now=NOW, fetch=broken_fetch)
    except OSError:
        pass
    else:
        raise AssertionError("a failed copy did not stop the pass")
    assert [c["method"] for c in rec2.calls] == ["GET"], rec2.calls

    # the real fetcher: credentials only to https on the space, and no redirects
    class FakeResponse:
        def __init__(self, body): self.body = body
        def read(self): return self.body
        def __enter__(self): return self
        def __exit__(self, *a): return False

    class FakeOpener:
        def __init__(self): self.requests = []
        def open(self, req, timeout=None):
            self.requests.append(req)
            return FakeResponse(b"RIFFdata")

    opener = FakeOpener()
    assert recipe.download(OLD1["url"], opener=opener) == b"RIFFdata"
    (req,) = opener.requests
    assert req.full_url == OLD1["url"] and req.get_method() == "GET", req.full_url
    assert req.get_header("Authorization") == "Basic " + base64.b64encode(b"proj-1234:PT-test").decode()
    for bad in ("http://example.signalwire.com/x.wav", "https://evil.example.com/x.wav"):
        try:
            recipe.download(bad, opener=opener)
        except ValueError:
            pass
        else:
            raise AssertionError(f"credentials would have gone to {bad}")
    assert len(opener.requests) == 1, "a refused URL must make no request"
    try:
        recipe.NoRedirects().redirect_request(req, None, 302, "Found", {}, "https://elsewhere.example.com/x")
    except urllib.error.HTTPError as e:
        assert e.code == 302, e
    else:
        raise AssertionError("a redirect was followed")

    # the spec's word on the two paths
    spec = V.spec("rest")
    V.assert_documented("rest", "GET", PATH, None)
    V.assert_documented("rest", "DELETE", f"{PATH}/{{id}}", None)
    delete = spec["paths"][f"{PATH}/{{id}}"]["delete"]
    assert "204" in delete["responses"], list(delete["responses"])
    listing = deref(spec, spec["paths"][PATH]["get"]["responses"]["200"]["content"]["application/json"]["schema"])
    assert "links" in listing["properties"], sorted(listing["properties"])
    items = deref(spec, deref(spec, listing["properties"]["data"])["items"])
    assert "oneOf" in items, "the spec's recording is a oneOf of call kinds"
    variants = [deref(spec, v) for v in items["oneOf"]]
    assert sorted(v.get("title", "") for v in variants) == \
        ["ConferenceRecording", "PstnRecording", "SipRecording", "WebRtcRecording"], \
        [v.get("title") for v in variants]
    for variant in variants:
        props = variant["properties"]
        assert {"id", "created_at", "url", "duration_in_seconds", "byte_size"} <= set(props), sorted(props)
        assert "recording file" in deref(spec, props["url"])["description"], props["url"]
    for fixture in (OLD1, FRESH, OLD2):
        assert set(fixture) <= set(variants[0]["properties"]), sorted(set(fixture) - set(variants[0]["properties"]))

    print(f"ok: two pages walked, {len(fetched)} expired recordings copied to {EXPORTS.name} "
          f"then deleted, each file complete before its DELETE; the 3-day-old one kept; a failed "
          f"copy made no DELETE; download sends basic auth only to https on the space")


if __name__ == "__main__":
    main()
