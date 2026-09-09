"""Send from a number group with sticky sender.

A number group is a pool of your numbers. The vendored REST spec documents
`sticky_sender` on the group as "Whether the number group uses the same 'From'
number for outbound requests to a number, or chooses a random one." You add
members by phone-number id. A send then names the group instead of a number.
The compat create-message reference describes `MessagingServiceSid` as "The
ID of a number group to use when sending the message." It adds "Either From
or MessagingServiceSid must be provided."
(https://signalwire.com/docs/compatibility-api/rest/messages/create-message)

Written against signalwire-sdk 3.0.1 (RestClient.number_groups,
RestClient.phone_numbers, RestClient.compat.messages).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def number_id(e164):
    """The resource id of a number on your project. `filter_number` is the
    spec's query for it; the exact comparison guards against a partial match."""
    for item in client.phone_numbers.list(filter_number=e164).get("data", []):
        if item.get("number") == e164:
            return item["id"]
    raise LookupError(f"{e164} is not a number on this project")


def create_pool(name, numbers):
    """A sticky-sender group holding `numbers`. Returns the group id.

    Every number is resolved before the group exists, so a number that is not
    on the project fails the call without leaving a half-built group behind."""
    ids = [number_id(e164) for e164 in numbers]
    group = client.number_groups.create(name=name, sticky_sender=True)
    for phone_number_id in ids:
        client.number_groups.add_membership(group["id"], phone_number_id=phone_number_id)
    return group["id"]


def send(group_id, to, body):
    """Name the group, not a number. The platform picks the From and, with
    sticky_sender, keeps picking the same one for this recipient."""
    return client.compat.messages.create(To=to, Body=body, MessagingServiceSid=group_id)


if __name__ == "__main__":
    import sys

    usage = ("usage: python app.py pool <name> <+1number> [+1number ...]\n"
             "       python app.py send <group_id> <+1to> <body words...>")
    verb, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    if verb == "pool" and len(args) >= 2:
        print(create_pool(args[0], args[1:]))
    elif verb == "send" and len(args) >= 3:
        print(send(args[0], args[1], " ".join(args[2:])))
    else:
        raise SystemExit(usage)
