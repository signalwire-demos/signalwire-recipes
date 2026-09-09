# Reconcile webhooks against the Logs API

> A pass over a time window walks every page of the voice and message logs. It reports every entry your webhook handler's store lacks, by the id the logs carry, and fetches the event trail of each such voice log.

**Scenario:** a nightly job that finds the calls and messages your status handler has no record of

## What this demonstrates

`GET /api/voice/logs` and `GET /api/messaging/logs` take `created_after`,
`created_before` and `page_size` in the vendored REST spec. When a page carries
`links.next`, the recipe passes that URL's query to the same list method. `GET /api/voice/logs/{id}/events`
answers with a `data` array of event entries. The spec requires `event_at`,
`level`, `name`, `details`, `project_id` and `log_id` on each. You reach them as
`client.logs.voice.list`,
`client.logs.messages.list` and `client.logs.voice.list_events`. You walk both
lists to the end, diff them against the ids your handler stored, and every id
the store lacks is a candidate to reconcile.

## How it works

```python
def every_page(fetch, **params):
    entries, page = [], fetch(**params)
    while True:
        entries.extend(page.get("data", []))
        nxt = (page.get("links") or {}).get("next")
        if not nxt:
            return entries
        page = fetch(**dict(parse_qsl(urlsplit(nxt).query)))

def reconcile(since, until):
    report = {"voice": [], "messages": []}
    for entry in missed(voice_logs(since, until)):
        report["voice"].append({"log": entry, "events": events_for(entry["id"])})
    report["messages"] = missed(message_logs(since, until))
    return report
```

What the platform receives for one pass over a two-page voice window:

```
GET /api/voice/logs?created_after=...&created_before=...&page_size=200
GET /api/voice/logs?page_token=...&page_size=200
GET /api/voice/logs/<first unseen id>/events
GET /api/voice/logs/<second unseen id>/events
GET /api/messaging/logs?created_after=...&created_before=...&page_size=200
```

`every_page` re-issues the query string each `links.next` carries, so it follows
whatever pagination the platform hands back. `SEEN` stands in for whatever your
webhook handler writes: a table of voice and message ids. Keep it per product,
so an id that appears in both cannot hide an entry. An id in the window that your
table lacks is an entry you have no record of. Why you have none is
for you to work out, and the events trail is where you start.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py 2026-09-01T00:00:00Z 2026-09-02T00:00:00Z
```

There is no server to expose; the script speaks to the REST API and exits.
Replace `SEEN` with a lookup into wherever your webhook handler records ids.
With it empty, the report lists every entry in the window.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder that answers with fixtures. They
are two voice pages, two message pages, and a trail per unseen call. In each
list, page one's `links.next` URL points at page two. You run a pass and
assert the following.

- the pass makes seven requests in order: voice page one, voice page two, one events request per unseen voice log, message page one, message page two
- page one of each list carries the window parameters, and page two of each carries exactly the query from its `links.next` URL
- the events requests carry no query, and each event in a trail carries every field the spec requires
- the spec documents every path and parameter used
- the report equals one expected object. It holds the three unseen voice logs whole, each with its own trail, the two unseen messages whole, and nothing the store holds
- judge a shared id within its product: the store holds the message id, so the pass excludes the message and reports the voice log
- one of the calls and one of the messages come from a second page
- the spec bounds `page_size` at exactly 1 and 1000 on both lists

## Limitations

The diff is by id: the pass compares each log entry's `id` with the ids your
handler stored. Neither callback document in the vendored specs states that
its `id` equals the log entry's `id`. Check both mappings against your own
account before trusting the report.

You prove the requests and the diff against fixtures; what the logs contain for
a real window is the platform's record.

A log entry's fields depend on its `type`. The spec's voice log is a oneOf over
Relay, Fabric, video room, Dialogflow and discarded shapes, and all of them
carry `id`.

## What to change first

Replace the body of `every_page` with `return fetch(**params).get("data", [])`
and run the verifier. The request sequence fails because the pass never fetches
a second page, and the report loses the voice log and the message that sat on
one. A window is every page, not the first one.
