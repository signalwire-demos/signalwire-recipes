# Commit a transaction from a call

> The agent collects, confirms, and then commits once through a single tool. The handler judges the confirmation against an allow-list of whole answers, and nothing reaches the order book before one. A second commit on the same call returns the first order's id.

**Scenario:** a bicycle shop taking accessory orders by phone

## What this demonstrates

Three tools, one write. `set_order` records the items in `global_data` and
marks the order unconfirmed. `confirm_order` takes an `answer` argument: the
words the model relays from the caller after the readback. The handler marks the
order confirmed only when it finds that answer in an allow-list of whole
phrases. `commit_order` writes to the order book once, and only when `confirmed`
is true in the `global_data` the platform posted with the call.

The model proposes each step and relays the words. The handlers decide whether
the step counts, from state they wrote themselves. No sequence of model calls
writes an order without an answer the code accepted as a yes.

## How it works

```python
def confirm_order(self, args, raw_data):
    order = raw_data.get("global_data", {}).get("order")
    if not order:
        return FunctionResult("INCOMPLETE: there is no order to confirm yet.")
    readback = f"{', '.join(order['items'])} for {order['total']:.2f}"
    if normalise(args.get("answer")) not in YES:
        return FunctionResult(f"NOT_A_YES: the caller did not clearly agree to {readback}.")
    r = FunctionResult(f"Confirmed: {readback}. You may commit it now.")
    r.add_action("set_global_data", {"confirmed": True})
    return r
```

`normalise` lower-cases the answer, expands "that's" and "it's", and drops
punctuation and four politeness words. The handler then looks the result
up in a set of whole answers. Membership, never substring: "yesterday" contains
"yes" and is not a yes, and neither is "I can't say yes". `commit_order` checks
three things in order: the book already has this `call_id`, there is an order,
and `confirmed` is true.

Every refusal is a response with no action, so the payload carries the reason
and changes nothing. `set_order` emits `"confirmed": false` alongside the order
every time:

```json
{"response": "Order noted: helmet, puncture-kit, total 101.50. Read it back ...",
 "action": [{"set_global_data": {"order": {"items": ["helmet", "puncture-kit"],
                                           "total": 101.5},
                                 "confirmed": false}}]}
```

A caller who confirms and then changes their mind therefore confirms again.
The order book is keyed by `call_id`, which makes the commit idempotent per
call: a repeated `commit_order` returns the id already on file.

The `items` parameter carries an `enum` of the catalogue. The handler drops
anything outside it anyway, and refuses a list with nothing left.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/orders/`, order a helmet, and answer the
readback with "yesterday".

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier threads `global_data` between tool calls the way the platform
does and asserts the order book after each step.

- the three tools render, and `set_order` carries the catalogue as an `enum`
- `commit_order` and `confirm_order` before any order each return `INCOMPLETE` with no action
- an empty item list, or one with nothing from the catalogue, returns `INVALID` with no action and leaves the session and the book untouched
- `set_order` drops an item outside the catalogue and emits the order with `confirmed: false`
- `commit_order` before confirmation returns `NOT_CONFIRMED`; the book is empty
- "yesterday", "no", "I can't say yes", "", "yes or no" and "sure thing" each return `NOT_A_YES` with no action
- "Yes, that's right." returns the exact readback response and `confirmed: true`
- changing the order after confirming resets `confirmed` to false, and the commit is refused again
- "Yes, thank you!" confirms, because politeness and punctuation are dropped before the lookup
- committing after a yes writes one order and returns its id
- a second commit on the same call returns `ALREADY_PLACED` with that id, and the book still holds one
- a second call id gets its own order

## Limitations

The handler judges the words it is given. The model relays them; nothing here
proves they are the caller's, and a stricter recipe would take the answer from
DTMF or a `prompt` the platform collected.

The yes-set is small on purpose, and "sure thing" is asked again. Extend `YES`
with whole phrases, never with substrings.

The order book is a dictionary in the process. Your version writes to a system
that can itself refuse a duplicate keyed by `call_id`, because a restart between
two commits would forget the first.

## What to change first

Delete the `NOT_CONFIRMED` check in `commit_order` and run the verifier. The
commit-before-confirmation assertion fails and the book has an order nobody
confirmed, which is the failure this recipe exists to prevent.
