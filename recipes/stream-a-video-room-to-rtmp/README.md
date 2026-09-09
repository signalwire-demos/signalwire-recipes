# Stream a video room to RTMP

> One POST to a room's streams path with a `url` asks the platform to stream the room's session to an RTMP or RTMPS server of yours. The stream id in the response is the handle: a PUT to the stream's path carries a new `url`, and a DELETE by id answers `204`.

**Scenario:** a workshop stand-up on video that a wider audience watches on a streaming platform

## What this demonstrates

The vendored REST spec, `tools/openapi/rest.json`, documents
`POST /api/video/rooms/{id}/streams` with one required field, `url`. Its
description reads "RTMP or RTMPS URL. This must be the address of a server
accepting incoming RTMP/RTMPS streams." The `201` response carries the stream's
`id`, `url` and `stream_type`. You then address the stream by that id. The spec
titles `PUT /api/video/streams/{id}` "Update stream" and requires the same
`url`, and titles `DELETE /api/video/streams/{id}` "Delete stream", answering
`204`. `GET /api/video/rooms/{id}/streams` lists a room's streams. You reach
the four as `rooms.create_stream`, `streams.update`, `streams.delete` and
`rooms.list_streams` under `client.video`.

## How it works

```python
def start_stream(room_id, url=None):
    url = url or RTMP_URL
    return client.video.rooms.create_stream(room_id, url=url)

def move_stream(stream_id, url):
    return client.video.streams.update(stream_id, url=url)

def stop_stream(stream_id):
    return client.video.streams.delete(stream_id)
```

What the platform receives:

```http
POST /api/video/rooms/<room_id>/streams
{"url": "rtmps://live.example.com/app/stream-key"}

PUT /api/video/streams/<stream_id>
{"url": "rtmp://backup.example.com/app/stream-key"}

DELETE /api/video/streams/<stream_id>
```

Keep the URL in `RTMP_URL` and out of the code, because it may contain a
stream key. The room is one you already have; the spec documents the
same `url` field on `POST /api/video/conferences/{id}/streams` for a prebuilt
conference.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials and RTMP_URL
ROOM_ID="your-room-id"           # from create-a-video-room-and-join-from-the-browser
python app.py start "$ROOM_ID"   # prints the stream, including its id
STREAM_ID="id-returned-by-start"
python app.py move "$STREAM_ID" rtmp://other.example.com/app/key
python app.py stop "$STREAM_ID"
python app.py list "$ROOM_ID"
```

You expose no server; the script speaks to the REST API and exits.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You swap the SDK's HTTP layer for a recorder that answers the stream create
with an id. You call the four helpers against a fixed room id and assert the
following.

- they make four requests in order: `POST` the stream, `PUT` the stream by id, `DELETE` the stream by id, `GET` the room's streams
- the create and the move are exactly `{"url": ...}`; the delete and the list carry no body
- the vendored spec documents every path and body, and requires exactly `url` on the create and the update
- the spec titles the `PUT` "Update stream" and the `DELETE` "Delete stream"
- the spec describes `url` as an RTMP or RTMPS URL, and its update body has exactly one property
- the create's `201` schema carries `id`, `url` and `stream_type`; the delete's `204` response says there is no content to send
- the spec requires the same `url` on the conference streams path
- with `RTMP_URL` unset, `start_stream` stops before any request

## Limitations

You prove the requests and the documented shapes. Whether frames reach your
RTMP server, when they start, and at what resolution are the platform's side of
a live session.

Creating the room is a different recipe,
`create-a-video-room-and-join-from-the-browser`. This one starts from a room
id.

## What to change first

Change `move_stream` to send `{"rtmp_url": url}` and run the verifier. The
exact-body assertion fails first, and `assert_documented` would fail next: the
spec's update body has exactly one property, and its name is `url`.
