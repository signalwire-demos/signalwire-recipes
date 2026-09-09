"""Register an E911 address for a number.

Two POSTs and one GET. `POST /api/relay/rest/addresses` creates the emergency
address, with the nine fields the spec requires and `emergency_enabled` on.
`GET /api/relay/rest/phone_numbers` finds the number's resource id.
`POST /api/relay/rest/phone_numbers/{id}/e911_address` attaches the address to
the number by the address's id. It was written for US addresses and US
numbers. The SDK wraps the first call as `client.addresses.create`. The attach
call has no wrapper in 3.0.1 (rest/namespaces/addresses.py), so this module
sends it through the same HTTP client the namespaces use.

Written against signalwire-sdk 3.0.1 (RestClient.addresses).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def create_address(label, first_name, last_name, street_number, street_name,
                   city, state, postal_code, country="US", *, address_type=None,
                   address_number=None, auto_correct_address=None):
    """The emergency address. The nine request fields the spec requires are the
    eight positional arguments plus `country`; the keyword-only three are its
    optional ones."""
    body = dict(label=label, country=country, first_name=first_name,
                last_name=last_name, street_number=street_number,
                street_name=street_name, city=city, state=state,
                postal_code=postal_code, emergency_enabled=True)
    for key, value in (("address_type", address_type),
                       ("address_number", address_number),
                       ("auto_correct_address", auto_correct_address)):
        if value is not None:
            body[key] = value
    return client.addresses.create(**body)


def number_id(e164):
    """The resource id of a number on your project. `filter_number` is the
    spec's query for it, so a project with many numbers still answers on the
    first page; the exact comparison guards against a partial match."""
    for item in client.phone_numbers.list(filter_number=e164).get("data", []):
        if item.get("number") == e164:
            return item["id"]
    raise LookupError(f"{e164} is not a number on this project")


def attach(phone_number_id, address_id):
    """Point a number at the address. rest/namespaces/addresses.py has no
    method for this path in 3.0.1, so it goes through the HttpClient every
    namespace shares (rest/client.py:74-85)."""
    return client.addresses._http.post(
        f"/api/relay/rest/phone_numbers/{phone_number_id}/e911_address",
        body={"e911_address_id": address_id})


def register(e164, **address):
    """The whole flow: create the address, find the number, attach the new
    address's id to it. Returns the attach response."""
    created = create_address(**address)
    return attach(number_id(e164), created["id"])


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        raise SystemExit("usage: python app.py +1XXXXXXXXXX <address_id>\n"
                         "create the address first with create_address() from a "
                         "Python shell, then attach it to your number here; or call "
                         "register(e164, **address) to do both")
    print(attach(number_id(sys.argv[1]), sys.argv[2]))
