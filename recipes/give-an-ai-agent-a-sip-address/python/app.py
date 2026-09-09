"""Give an AI agent a SIP address.

A hosted resource can be reached over SIP as well as from a phone number.
`POST /api/fabric/sip_addresses` requires a URL-safe `name` and the
`calling_handler_resource_id` of the resource to ring, and the response carries
the `uri` a SIP phone or PBX dials. The `user` part defaults to `*`, which
accepts any username.

3.0.1 has no wrapper for this path, so the request goes through the HTTP client
every namespace shares (rest/client.py).

Written against signalwire-sdk 3.0.1 (RestClient).

    python app.py <agent_resource_id> front-desk
"""
import re
import sys

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN / SIGNALWIRE_SPACE from the env
client = RestClient()
http = client._http

# the spec: lowercase letters, numbers and hyphens, nothing else
NAME_SHAPE = re.compile(r"^[a-z0-9-]+$")


def give_address(resource_id, name, user=None, encryption="required"):
    """Create a SIP address that rings the resource. Returns the platform's record."""
    if not NAME_SHAPE.match(name):
        raise ValueError(f"name must be lowercase letters, numbers and hyphens: {name!r}")
    body = {"name": name, "calling_handler_resource_id": resource_id,
            "encryption": encryption}
    if user:
        # otherwise the spec's default `*` accepts any username
        body["user"] = user
    return http.post("/api/fabric/sip_addresses", body=body)


def dial_string(created):
    """What to type into the SIP phone."""
    return created["uri"]


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
    else:
        made = give_address(args[0], args[1], *args[2:3])
        print(dial_string(made))
