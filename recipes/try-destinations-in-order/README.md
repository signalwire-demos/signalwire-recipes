# Dial destinations in order or all at once, with a failure path

> One `connect` carries a `serial` list to dial in order, or a `parallel` list to dial at once. `result` runs when the bridge ends, and its `failed` branch is the failure path.

**Scenario:** a shop line that hunts through the counter, the workshop's SIP phone and the owner's mobile

## What this demonstrates

One `connect` verb carries the whole hunt. The
[connect reference](https://signalwire.com/docs/swml/reference/connect)
describes `serial` as destinations "to dial in order", each "tried
sequentially". It describes `parallel` as destinations "to dial
simultaneously", where "the first destination to answer is bridged and the
rest are cancelled". The `to` field accepts phone numbers, SIP URIs and
Resource addresses; this list mixes the first two.

When the bridge ends, `result` runs against `connect_result`, which the
reference gives as `connected` or `failed`, with `connect_failed_reason`
carrying the "detailed reason for failure". The `failed` case is the failure
path, whatever the reason.

## How it works

```yaml
- connect:
    timeout: 15
    serial:
      - { to: "+15550100001" }
      - { to: "sip:workshop@pbx.example.com" }
      - { to: "+15550100003" }
    result:
      case:
        connected:
          - play: { url: "say:Thanks for calling Ridgeline Cycles. Goodbye." }
          - hangup: {}
        failed:
          - play: { url: "say:Nobody could take your call. Please try again later." }
          - hangup: {}
```

`result` runs "once the peer leg of the call has ended", per the reference. For
`connected` that is after the conversation; for `failed` it is after the last
destination fails. The `parallel` section dials the two phone numbers together
and keeps only a `failed` branch.

The schema defines `connect` as a oneOf over four shapes: a single `to`, a
`serial` list, a `parallel` list, or `serial_parallel`. A verb carrying both `to`
and `serial` fails validation, which the verifier shows.

The Python surface builds the same document with `SWMLService`, reading the list
from `DESTINATIONS`. The verifier asserts the two documents are equal.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set DESTINATIONS and RING_SECONDS
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 8080 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/hunt/`, call, and let the first destination ring out.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

It validates both surfaces against the bundled schema and asserts the following.

- the main section is `answer`, `play`, `connect`, and the connect has no single `to`
- `serial` holds the three destinations in the configured order, with a 15 second `timeout`
- `result.case` has exactly `connected` and `failed`, and each branch is a `play` then a `hangup`
- the `parallel` section carries the two phone numbers and keeps a `failed` branch
- the Python surface and the YAML surface render the same document
- a connect carrying both `to` and `serial` fails schema validation

## Limitations

The verifier proves the document, not the dialling. On a live call,
`connect_failed_reason` carries the detail when the connect fails; this recipe
does not read it.

A `queue:` destination needs `transfer_after_bridge`, per the reference, and is
not part of this list.

## What to change first

Swap the first two `serial` entries in both surfaces and run the verifier. The
order assertion fails, which is the point: the list is the hunt order, and
nothing else decides it.
