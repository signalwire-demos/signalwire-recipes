# Send a batch within your rate limit

> A batch goes out one message per interval for the number type's documented rate. Requests start at the published nominal interval; what the platform then delivers, and when, is its side.

**Scenario:** a bike shop texting two hundred customers that the spring service special is on, from one 10DLC number

## What this demonstrates

The rate limits page, https://signalwire.com/docs/platform/rate-limits, gives
messaging throughput per number type. 10DLC is "4 MPS", toll-free is "3
messages per second (MPS)", short codes are "10 MPS", and the queue holds
"10,000 queued messages". Past the rate, SignalWire queues messages in the
order received. Once the backlog is full, "SignalWire will stop adding to the
Messaging queue". So sending faster than the rate buys nothing, and a burst
large enough to fill the queue loses what did not fit. You send one message
per interval instead, so the queue never builds. Each message is a
`POST /api/messaging/messages` with `to`, `from` and `body`, the vendored REST
spec's two required fields and the text.

## How it works

```python
LIMITS = {"10dlc": 4, "toll-free": 3, "short-code": 10}   # messages per second
BACKLOG = 10_000

def send_batch(recipients, body, number_type=NUMBER_TYPE, clock=time.monotonic, sleep=time.sleep):
    if len(recipients) > BACKLOG:
        raise ValueError(...)
    interval = 1 / LIMITS[number_type]
    next_at = clock()
    for to in recipients:
        now = clock()
        if now < next_at:
            sleep(next_at - now)
        results.append(http.post("/api/messaging/messages", body={"to": to, "from": FROM, "body": body}))
        next_at = max(now, next_at) + interval
```

What the platform receives, once per recipient, a quarter of a second apart on
a 10DLC number:

```json
POST /api/messaging/messages
{"to": "+1555YYYYYYY", "from": "+1555XXXXXXX", "body": "Your bike is ready for pickup."}
```

`next_at` moves forward by the interval from the later of now and the previous
slot. The clock is read again after a sleep, so a sleep that overshoots pushes
the next slot out instead of letting two sends land close together. A slow
response does not let the next send catch up in a burst either. The clock and
the sleep are arguments, so the verifier can run the pacer against a fake
clock.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: credentials, SMS_FROM and NUMBER_TYPE
python app.py "The spring service special is on." +1XXXXXXXXXX +1XXXXXXXXXY
```

There is no server to expose; the script speaks to the REST API and exits,
printing each message's id, destination and status. Two hundred recipients on
a 10DLC number take about fifty seconds, which is the point.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You swap the SDK's HTTP layer for a recorder and the clock for one that moves
only when the pacer sleeps. You send ten messages at the 10DLC rate and assert
the following.

- the app's rates equal the verifier's own numbers from the rate limits page
- ten `POST`s go to the documented messages path, each with exactly `to`, `from` and `body`, and the body is documented
- the clock reads at the ten sends are exactly 0.25 seconds apart, the batch spans 2.25 seconds, and the pacer slept nine times for 0.25
- the platform's responses come back in order
- four messages at the toll-free rate are a third of a second apart
- with a sleep that overshoots by 50 ms every time, no two sends are closer than the interval
- with a platform that takes 0.4 seconds to answer each request, sends are 0.4 seconds apart and never bunch up to catch up
- an unknown number type raises before any request

## Limitations

You prove the pacing and the requests against a fake clock. The rates are the
page's published figures, and the page says actual 10DLC throughput "may be
lower or higher depending on carrier and TCR limits". Delivery is the
platform's and the carriers' side.

You run one pacer per number. Two processes sending from the same number each
pace themselves and together exceed the rate; put the batch behind one queue.

## What to change first

Change the 10DLC rate in `LIMITS` to 5 and run the verifier. The first
assertion fails, because the verifier carries the page's numbers itself. The
platform's limit does not move when yours does.
