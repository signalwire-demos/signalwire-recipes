# Transfer a call

> A live call is bridged to a number, SIP URI or Resource address, and optionally returns when the far end hangs up.

**Scenario:** a front desk that connects callers to a colleague and takes the call back if they hang up first

## What this demonstrates

`connect` is the transfer verb. Its `to` can be a phone number, a `sip:` URI or
a Resource address such as `/public/support`. Execution pauses while the two
legs are bridged; when the far end hangs up, the verbs *after* `connect` run.
That is the return path, and it is where the caller can be offered something
else. `transfer_after_bridge: "true"` makes the transfer permanent instead.

## How it works

```yaml
- answer: {}
- play: { url: "say:Please hold while I connect you." }
- connect: { to: "+1555...", timeout: 20, ringback: ["ring:us"] }
- play: { url: "say:The other party has left the call. Thank you for calling." }   # return path
- hangup: {}
```

The `sip` section is the SIP variant: the same `connect` with a `sip:` URI and
`headers`, which SignalWire stamps onto the INVITE so your PBX can route on them.

```yaml
- connect:
    to: "sip:support@pbx.example.com"
    headers:
      - { name: "X-Account-Id", value: "acct-1234" }
```

To try several destinations in order or ring them at once, replace `to` with
`serial` or `parallel`. See `try-destinations-in-order`. To brief the person
before the bridge completes, add `confirm`. See
`brief-the-human-before-the-bridge-completes`.

## Run it

Markup only: paste `swml/agent.yaml` into a SWML Script, replace the
destinations, assign a phone number.

Python:

```bash
cd python
pip install -r requirements.txt
TRANSFER_TO=+1555... python app.py            # temporary: the call comes back
PERMANENT=true TRANSFER_TO=+1555... python app.py
```

Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/transfer/`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

Both surfaces validate against the SWML schema. The verifier asserts `connect` is
followed by a return path, that `PERMANENT=true` adds `transfer_after_bridge`, and
that the SIP variant carries the custom headers.

## What to change first

Change `to` to a Resource address (`/public/<name>`) and route the call into a
SWML script, an AI agent or a subscriber's browser instead of a phone.
