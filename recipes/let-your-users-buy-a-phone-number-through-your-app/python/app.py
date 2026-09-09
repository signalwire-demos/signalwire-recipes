"""Let your users buy a phone number through your app.

Onboarding uses your credentials: `POST /api/projects` creates the tenant's
subproject and `POST /api/project/tokens` issues a token bound to it. Every
number request after that goes through a second RestClient built from the
tenant's own credentials, so your platform token is never used on their behalf.

Written against signalwire-sdk 3.0.1 (RestClient, RestClient.phone_numbers).

    python app.py onboard "Acme Dental"
    python app.py offer "Acme Dental" 415
    python app.py buy "Acme Dental" +14155550123 https://your-host/acme/
    python app.py numbers "Acme Dental"
    python app.py release "Acme Dental" <number_id>
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# your own credentials, used for onboarding and nothing else
platform = RestClient()
SPACE = os.environ["SIGNALWIRE_SPACE"]

# stands in for the table where you keep each tenant's credentials
TENANTS_PATH = Path(os.getenv("TENANTS_PATH", "tenants.json"))

# what a tenant's token may do. management is deliberately absent, so the token
# cannot create further projects or tokens
PERMISSIONS = ["numbers", "calling", "messaging"]


def _load():
    if not TENANTS_PATH.exists():
        return {}
    return json.loads(TENANTS_PATH.read_text(encoding="utf-8"))


def _save(tenants):
    tmp = TENANTS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(tenants, indent=2), encoding="utf-8")
    os.replace(tmp, TENANTS_PATH)


def onboard(name, permissions=PERMISSIONS):
    """Create the tenant's subproject and a token bound to it. Stores both."""
    # 3.0.1 wraps the tokens path (client.project.tokens) but not POST
    # /api/projects, so the subproject goes through the HTTP client every
    # namespace shares (rest/client.py)
    project = platform._http.post("/api/projects",
                                  body={"name": name, "force_https_requests": True})
    token = platform.project.tokens.create(name=f"{name} numbers",
                                           permissions=list(permissions),
                                           subproject_id=project["id"])
    # token_id is the only handle for PATCH or DELETE later: the spec
    # documents no way to list a project's tokens
    record = {"name": name, "project_id": project["id"], "token_id": token["id"],
              "permissions": token["permissions"], "token": token["token"]}
    tenants = _load()
    tenants[name] = record
    # the token is shown once, so it is stored here at that moment
    _save(tenants)
    return record


def tenant(name):
    """The stored record for one tenant."""
    record = _load().get(name)
    if record is None:
        raise KeyError(f"{name} has not been onboarded")
    return record


def as_tenant(record):
    """A client that authenticates as the tenant. Never falls back to yours."""
    if not record.get("project_id") or not record.get("token"):
        raise ValueError("no tenant credentials; refusing to act as the platform")
    return RestClient(project=record["project_id"], token=record["token"],
                      host=SPACE)


def offer(record, areacode, max_results=5):
    """Numbers the tenant can pick from. Returns E.164 strings."""
    found = as_tenant(record).phone_numbers.search(areacode=areacode,
                                                   number_type="local",
                                                   max_results=max_results)
    return [n["number"] for n in found.get("data", [])]


def buy(record, number, webhook_url):
    """Purchase the number into the tenant's subproject and point it at them."""
    client = as_tenant(record)
    bought = client.phone_numbers.create(number=number)
    client.phone_numbers.update(bought["id"], name=record["name"],
                                call_handler="relay_script",
                                call_relay_script_url=webhook_url)
    return bought


def numbers(record):
    """The first page of the tenant's numbers. Page with `page_size`."""
    return as_tenant(record).phone_numbers.list()


def release(record, number_id):
    """Give the number back when the tenant cancels."""
    return as_tenant(record).phone_numbers.delete(number_id)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "help"
    rest = args[1:]
    if not rest:
        print(__doc__)
    elif cmd == "onboard":
        print(onboard(rest[0]))
    elif cmd == "offer":
        for number in offer(tenant(rest[0]), rest[1]):
            print(number)
    elif cmd == "buy":
        print(buy(tenant(rest[0]), rest[1], rest[2]))
    elif cmd == "numbers":
        print(numbers(tenant(rest[0])))
    elif cmd == "release":
        print(release(tenant(rest[0]), rest[1]))
    else:
        print(__doc__)
