# Send from a number group with sticky sender

> When you create a number group with `sticky_sender: true`, the platform picks From numbers out of that pool and holds one per recipient. A compat send names the group as `MessagingServiceSid` and carries no `From`.

**Scenario:** a bike shop texting repair updates from several numbers, where each customer should keep seeing the same one

## What this demonstrates

Three documented pieces. `POST /api/relay/rest/number_groups` creates the
group. The vendored REST spec requires `name` and documents `sticky_sender` as
a boolean, default false. Its description is "Whether the number group uses the
same 'From' number for outbound requests to a number, or chooses a random one".
`POST /api/relay/rest/number_groups/{id}/number_group_memberships` adds a
member by `phone_number_id`, its one required field. Then the compat create
message takes the group in place of a number.
https://signalwire.com/docs/compatibility-api/rest/messages/create-message
describes `MessagingServiceSid` as "The ID of a number group to use when
sending the message". It adds "Either From or MessagingServiceSid must be
provided".

The SDK wraps the first two as `client.number_groups.create` and
`add_membership`, and the send as `client.compat.messages.create`.

## How it works

```python
def create_pool(name, numbers):
    ids = [number_id(e164) for e164 in numbers]          # resolve first, so a bad number fails early
    group = client.number_groups.create(name=name, sticky_sender=True)
    for phone_number_id in ids:
        client.number_groups.add_membership(group["id"], phone_number_id=phone_number_id)
    return group["id"]

def send(group_id, to, body):
    return client.compat.messages.create(To=to, Body=body, MessagingServiceSid=group_id)
```

What the platform receives:

```http
POST /api/relay/rest/number_groups
{"name": "repair-updates", "sticky_sender": true}

POST /api/relay/rest/number_groups/<group_id>/number_group_memberships
{"phone_number_id": "<id of +1555XXXXXXX>"}

POST /api/laml/2010-04-01/Accounts/<project>/Messages
{"To": "+1555YYYYYYY", "Body": "Your bike is ready.", "MessagingServiceSid": "<group_id>"}
```

Membership takes a phone number's resource id, not its digits, so `number_id`
looks it up with the spec's `filter_number` query and compares the number
exactly. The send has no `From`. Which member number the recipient sees is the
platform's choice, and `sticky_sender` is what makes that choice hold for them.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # then edit .env: your project id, API token and space
python app.py pool repair-updates +1XXXXXXXXXX +1XXXXXXXXXY    # prints the group id
python app.py send <group_id> +1YYYYYYYYYY "Your bike is ready."
```

Use two or more numbers on your project to see the selection; the command
accepts one, which makes a group with nothing to choose between. There is no server to expose; the script speaks to the REST API
and exits. Send twice to one recipient and compare the From numbers in the
messaging log.

## Verify it

No network, no account.

```bash
cd ..                     # back to the recipe folder
python verify.py
```

You swap the SDK's HTTP layer for a recorder. It answers the group create with
an id, and each number lookup with a near miss followed by the exact number.
You build a two-number pool and send twice to one recipient, and assert the
following.

- the group create is one `POST` to the documented path with exactly `name` and `sticky_sender: true`
- you look up every number before you create the group, one `GET` of the phone numbers list each with exactly `filter_number`
- each number then costs one `POST` to the documented memberships path
- that membership body is exactly the id of the exact number, not the near miss the lookup listed first
- both sends are `POST`s to the documented compat messages path. Each equals one literal body: `To`, its own `Body`, and a `MessagingServiceSid` equal to the group id
- the spec requires `name` on the group, `phone_number_id` on the membership, and only `To` on the message
- the spec documents `sticky_sender` as a boolean defaulting to false with the full quoted description
- `From`'s description in the spec says either it or `MessagingServiceSid` must be provided

## Limitations

You prove the requests. The pin itself, one From per recipient, is the
platform's behaviour and shows only in a live messaging log.

The vendored compat spec describes `MessagingServiceSid` only as a UUID. The
sentence naming it as a number group id is from the live reference page linked
above, fetched on 2026-09-02.

## What to change first

Pass `sticky_sender=False` in `create_pool` and run the verifier. The exact-body
assertion fails. The spec's default says why nothing else would: false is what
you get when you do not ask, and then the platform "chooses a random one".
