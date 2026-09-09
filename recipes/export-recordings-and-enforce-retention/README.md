# Export recordings and enforce retention

> A pass lists every call recording across pages, copies each one older than your retention window to storage you control, and then deletes it from SignalWire. The pass deletes only what it copied first, whole.

**Scenario:** a shop that must keep call recordings for a year in its own archive and nowhere else

## What this demonstrates

The vendored REST spec lists recordings at `GET /api/relay/rest/recordings`,
with a `links` object for paging and no query parameters of its own. Every
variant of recording it documents carries an `id`, a `created_at`, a
`duration_in_seconds` and a `url` "of the recording file".
Each variant also carries a `byte_size`, which is how the pass knows a copy is
whole. `DELETE /api/relay/rest/recordings/{id}` answers `204`. Retention is
therefore three steps in a fixed order: find what is past the window, copy it
out, delete it. The copy is a GET of
`url` with your project credentials as basic auth. The media protection page,
https://signalwire.com/docs/platform/media-protection, says protected media
requires them. You reach the two endpoints as `client.recordings.list` and
`client.recordings.delete`.

## How it works

```python
def export_and_delete(now=None, fetch=download):
    now = now or datetime.now(timezone.utc)
    moved = []
    for recording in every_page(client.recordings.list):
        if not expired(recording, now):
            continue
        suffix = pathlib.PurePosixPath(urlsplit(recording["url"]).path).suffix or ".wav"
        path = EXPORT_DIR / f"{recording['id']}{suffix}"
        path.write_bytes(fetch(recording["url"]))     # copy first
        client.recordings.delete(recording["id"])      # then, and only then, delete
        moved.append({"id": recording["id"], "created_at": recording["created_at"],
                      "path": str(path)})
    return moved
```

What the platform receives, per expired recording:

```json
GET /api/relay/rest/recordings
GET /api/relay/rest/recordings?page_token=<from links.next>
GET <url>                                 with basic auth
DELETE /api/relay/rest/recordings/<id>    204
```

The order is the safety property. A copy that raises stops the pass on that
recording, before its `DELETE`, so a storage outage leaves recordings in
SignalWire rather than nowhere. `EXPORT_DIR` stands in for your object storage;
swap `write_bytes` for your client's upload. `download` sends the credentials
only to an `https` URL on your own space and refuses to follow a redirect. A
`url` that pointed elsewhere would get nothing. A fetched body whose length is
not the recording's `byte_size` stops the pass before it writes or deletes.
The script refuses `RETENTION_DAYS` below one at startup, because a zero
window would delete everything.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, RETENTION_DAYS, EXPORT_DIR
python app.py
```

There is no server to expose; the script speaks to the REST API and exits. Run
it from a scheduler. It prints one line per recording moved, from the list
`export_and_delete` returns: the id, `created_at`, and the copy's path.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder that answers with two pages of
recordings, two past a 30-day window and one inside it. You swap the media
fetcher for a fake that records its URLs. You run a pass and assert the following.

- the pass makes `GET`, `GET`, `DELETE`, `DELETE` in that order; page two carries exactly the query from `links.next`
- one event stream records every copy and every delete: at the moment of each `DELETE`, the recording's whole body is on disk
- the pass asked the fetcher for exactly the two expired URLs, and each copy sits in the export directory under its id with the file's own extension
- the pass neither fetched nor deleted the fresh recording, and the returned report is exactly the two moved records, with id, `created_at` and path
- a pass whose fetcher returns one byte short of `byte_size` stops with an error, writes no file and makes no `DELETE`
- a fresh interpreter with `RETENTION_DAYS=0` exits at import with the refusal message
- a second pass whose fetcher raises makes no `DELETE`
- `download` sends one GET with your project credentials as basic auth to an `https` URL on your space, and refuses `http`, another host, and a redirect
- every path is documented, the delete answers `204`, the list carries `links`, and the spec's four recording variants each carry `id`, `created_at`, `url`, `duration_in_seconds` and `byte_size`

## Limitations

You prove the order and the requests. What `url` serves, and how long the
platform takes to mark a recording `finished`, are the platform's side.

Writing a recording somewhere else at record time is a different mechanism. The
cXML `<Record>` reference documents `storageUrl` for that
(https://signalwire.com/docs/compatibility-api/cxml/reference/voice/record).
The bundled SWML schema's `record` and `record_call` have no storage field,
which is why this recipe works after the fact.

## What to change first

Swap the two lines marked `copy first` and `then, and only then, delete`, and
run the verifier. The failing-fetch case shows a `DELETE` for a recording that
was never copied, which is the failure this recipe exists to prevent.
