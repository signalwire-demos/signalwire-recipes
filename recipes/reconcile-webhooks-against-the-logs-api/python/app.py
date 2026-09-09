"""Reconcile webhooks against the logs API.

Your host can miss a status webhook: it was down, a proxy timed out, a deploy
was mid-flight. The voice and message logs list what the platform recorded. A
scheduled pass over a time window walks every page of both lists and reports
every entry your handler's store lacks, as candidates to reconcile.
`GET /api/voice/logs` and `GET /api/messaging/logs` take `created_after` and
`created_before`. Each voice log's events are one more GET away.

Written against signalwire-sdk 3.0.1 (RestClient.logs).
"""
from urllib.parse import parse_qsl, urlsplit

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()

# What your webhook handler recorded, one set per product so a voice id and a
# message id that happen to match cannot hide each other. A real one is a
# table; the reconciler only needs membership.
SEEN = {"voice": set(), "messages": set()}


def every_page(fetch, **params):
    """Walk a list to its end. Each page's `links.next` is a URL whose query
    carries the next page's parameters, so the walk re-issues the query the URL
    supplies. The spec's page_size maximum is 1000."""
    entries = []
    page = fetch(**params)
    while True:
        entries.extend(page.get("data", []))
        nxt = (page.get("links") or {}).get("next")
        if not nxt:
            return entries
        page = fetch(**dict(parse_qsl(urlsplit(nxt).query)))


def voice_logs(since, until, page_size=200):
    """Every voice log the platform kept for the window, all pages."""
    return every_page(client.logs.voice.list, created_after=since,
                      created_before=until, page_size=page_size)


def message_logs(since, until, page_size=200):
    """Every message log for the window, all pages."""
    return every_page(client.logs.messages.list, created_after=since,
                      created_before=until, page_size=page_size)


def missed(entries, product):
    """Entries your store lacks for this product: the candidates to reconcile."""
    return [entry for entry in entries if entry.get("id") not in SEEN[product]]


def events_for(log_id):
    """The event trail of one voice log, for the ones you missed."""
    return client.logs.voice.list_events(log_id)


def reconcile(since, until):
    """One pass: list the window, diff against what you saw, fetch the trail
    of each missed call."""
    report = {"voice": [], "messages": []}
    for entry in missed(voice_logs(since, until), "voice"):
        report["voice"].append({"log": entry, "events": events_for(entry["id"])})
    report["messages"] = missed(message_logs(since, until), "messages")
    return report


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) != 3:
        raise SystemExit("usage: python app.py <since ISO-8601> <until ISO-8601>")
    print(json.dumps(reconcile(sys.argv[1], sys.argv[2]), indent=1))
