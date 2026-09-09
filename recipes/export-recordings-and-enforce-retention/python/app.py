"""Export recordings and enforce retention.

SignalWire keeps call recordings until you delete them. The vendored REST spec
lists them at `GET /api/relay/rest/recordings`, each with an `id`, a
`created_at`, a `url` "of the recording file" and a `duration_in_seconds`, and
removes one with `DELETE /api/relay/rest/recordings/{id}`, which answers 204.
A pass here walks every page, copies each recording older than your retention
window to storage you control, and only then deletes it. Nothing is deleted
that was not copied first.

The copy is a plain HTTP GET of `url`, sent with your project credentials as
basic auth so it also works when the project's media protection is on.

Written against signalwire-sdk 3.0.1 (RestClient.recordings).
"""
import base64
import os
import pathlib
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlsplit

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", "30"))
if RETENTION_DAYS < 1:
    raise SystemExit("RETENTION_DAYS must be at least 1; a zero or negative window "
                     "would delete every recording")
EXPORT_DIR = pathlib.Path(os.getenv("EXPORT_DIR", "exports"))
# the only host that gets your credentials: your own space
SPACE = os.environ["SIGNALWIRE_SPACE"]


def every_page(fetch, **params):
    """Walk a list to its end. Each page's `links.next` is a URL whose query
    carries the next page's parameters, so the walk re-issues that query."""
    entries = []
    page = fetch(**params)
    while True:
        entries.extend(page.get("data", []))
        nxt = (page.get("links") or {}).get("next")
        if not nxt:
            return entries
        page = fetch(**dict(parse_qsl(urlsplit(nxt).query)))


class NoRedirects(urllib.request.HTTPRedirectHandler):
    """Credentials go to the URL you were given and nowhere it points onward."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


OPENER = urllib.request.build_opener(NoRedirects)


def download(url, opener=None):
    """Fetch the media with project credentials as basic auth, which the media
    protection page says protected media requires. The credentials go only to
    an https URL on your own space, and never follow a redirect."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != SPACE:
        raise ValueError("refusing to send credentials to "
                         f"{parts.scheme}://{parts.hostname}")
    creds = f"{os.environ['SIGNALWIRE_PROJECT_ID']}:{os.environ['SIGNALWIRE_API_TOKEN']}"
    req = urllib.request.Request(url, headers={
        "Authorization": "Basic " + base64.b64encode(creds.encode()).decode()})
    with (opener or OPENER).open(req, timeout=120) as response:
        return response.read()


def expired(recording, now):
    created = datetime.fromisoformat(recording["created_at"].replace("Z", "+00:00"))
    return created < now - timedelta(days=RETENTION_DAYS)


def export_and_delete(now=None, fetch=download):
    """One pass. Returns what moved, in order. A failed copy stops the pass
    before that recording is deleted."""
    now = now or datetime.now(timezone.utc)
    moved = []
    for recording in every_page(client.recordings.list):
        if not expired(recording, now):
            continue
        suffix = pathlib.PurePosixPath(urlsplit(recording["url"]).path).suffix or ".wav"
        body = fetch(recording["url"])                 # copy first
        # the spec's recording carries byte_size; a short body is a truncated
        # copy, and the pass stops before writing it and before any delete
        if "byte_size" in recording and len(body) != recording["byte_size"]:
            raise ValueError(f"{recording['id']}: fetched {len(body)} bytes, "
                             f"expected {recording['byte_size']}; nothing deleted")
        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        path = EXPORT_DIR / f"{recording['id']}{suffix}"
        path.write_bytes(body)
        client.recordings.delete(recording["id"])      # then, and only then, delete
        moved.append({"id": recording["id"], "created_at": recording["created_at"],
                      "path": str(path)})
    return moved


if __name__ == "__main__":
    for item in export_and_delete():
        print(item)
