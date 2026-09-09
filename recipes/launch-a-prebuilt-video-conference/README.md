# Launch a prebuilt video conference

> One POST creates a themed video conference from a `display_name` and the options the spec documents. One GET lists the tokens the spec documents for it, each with a name, a token and scopes.

**Scenario:** a workshop that wants a video room in its own colours without building a room UI

## What this demonstrates

You `POST /api/video/conferences` to create a prebuilt conference, themed with
the colour fields the vendored REST spec lists. Those are `light_primary`,
`dark_primary`, and the background, foreground, success and negative colours
for each theme. `display_name` is the one required field. `name`, `quality`,
`layout`, `record_on_start`, `join_from`, `join_until` and `enable_chat` are
among the options. The spec's `200` response schema carries the `id` you pass to
`GET /api/video/conferences/{id}/conference_tokens`, which lists its tokens.
The spec's token schema carries `name`, `token` and `scopes`. You reach both
as `client.video.conferences.create` and
`client.video.conferences.list_conference_tokens`. The SignalWire reference
describes these conferences as a prebuilt UI with no code required
(https://signalwire.com/docs/apis/rest/video/video-conferences/create-video-conference).

## How it works

```python
def launch(display_name, *, name=None, record_on_start=False, quality="720p",
           layout="grid-responsive", primary="#F72A72", join_from=None, join_until=None):
    body = {"display_name": display_name, "record_on_start": record_on_start,
            "quality": quality, "layout": layout,
            "light_primary": primary, "dark_primary": primary}
    for key, value in (("name", name), ("join_from", join_from), ("join_until", join_until)):
        if value:
            body[key] = value
    return client.video.conferences.create(**body)

def tokens(conference_id):
    return client.video.conferences.list_conference_tokens(conference_id)
```

What the platform receives:

```json
POST /api/video/conferences
{"display_name": "Workshop stand-up", "name": "workshop-standup",
 "record_on_start": true, "quality": "720p", "layout": "grid-responsive",
 "light_primary": "#F72A72", "dark_primary": "#F72A72",
 "join_from": "2026-09-03T09:00:00Z", "join_until": "2026-09-03T10:00:00Z"}

GET /api/video/conferences/<id>/conference_tokens
```

You pass the `id` from the create response to the token listing. Each token
carries `scopes`, which the spec describes as "a list of permissions". The spec also
documents `POST /api/video/conference_tokens/{id}/reset`, titled "Reset
conference token", for a token you need to invalidate.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py "Workshop stand-up" workshop-standup
```

There is no server to expose; the script speaks to the REST API and exits. You
see the conference, then its tokens.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

You swap the SDK's HTTP layer for a recorder that answers the create with an id
and the token list with one token. You call both helpers and assert the
following.

- `launch` makes one `POST` to the documented conferences path
- its body equals one expected object: `display_name`, `name`, `record_on_start`, `quality`, `layout`, the two primary colours, `join_from` and `join_until`
- every key in that body is a documented property, the spec's required list is exactly `display_name`, and the `200` schema carries `id`
- `tokens` makes one `GET` to the documented conference tokens path for the id the create returned, with no query
- it returns the recorder's whole page, `links` and `data`
- a second launch with a different quality, layout and colour, and no name or join window, sends exactly those six keys
- the spec's token schema carries `id`, `name`, `token` and `scopes`

## Limitations

You prove the requests and the documented shapes. Which tokens a real
conference has, and what each one's `scopes` hold, appear only in the live
response.

The conference UI is the platform's, per the reference above. For a room UI you
build yourself, see `create-a-video-room-and-join-from-the-browser`.

## What to change first

Remove `display_name` from the body and run the verifier. The exact-body
assertion fails, and the spec's required list says why: it is the one thing a
conference cannot do without.
