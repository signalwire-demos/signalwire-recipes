"""Prove the claim without a network.

Claim: a number group created with `sticky_sender: true` is a pool the
platform picks From numbers out of, holding one per recipient. A compat send
names the group as `MessagingServiceSid` and carries no `From`.

Proof: the HTTP layer is a recorder. `create_pool` makes one POST to the
documented number groups path with exactly `name` and `sticky_sender: true`.
Before that it makes one GET of the phone numbers list per number, filtered
to it, and afterwards one POST to the documented memberships path with the
exact number's id, not the near miss listed first. `send`, twice to the same recipient, makes
two POSTs to the documented compat messages path, each equal to a literal body
naming the group as `MessagingServiceSid`. The spec requires `name` on the
group, `phone_number_id` on the membership and only `To` on the message. It
documents `sticky_sender` as a boolean defaulting to false. Expected values
live here, not in app.py.
"""
import os
import pathlib
import sys

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "SIGNALWIRE_PROJECT_ID": "proj-1234",
    "SIGNALWIRE_API_TOKEN": "PT-test",
    "SIGNALWIRE_SPACE": "example.signalwire.com",
})

import verifylib as V  # noqa: E402

GROUPS = "/api/relay/rest/number_groups"
NUMBERS = "/api/relay/rest/phone_numbers"
MESSAGES = "/api/laml/2010-04-01/Accounts/proj-1234/Messages"
GID = "3f2e1d0c-9b8a-4765-8321-0fedcba98765"
POOL = {"+15550001111": "1a2b3c4d-0000-4000-8000-000000000001",
        "+15550001112": "1a2b3c4d-0000-4000-8000-000000000002"}
TO = "+15550002222"


def deref(spec, node):
    schemas = spec["components"]["schemas"]
    while isinstance(node, dict) and "$ref" in node:
        node = schemas[node["$ref"].split("/")[-1]]
    return node


def body_schema(spec, path, method="post"):
    op = spec["paths"][path][method]
    return deref(spec, op["requestBody"]["content"]["application/json"]["schema"])


def main():
    V.sdk_banner()
    import app as recipe

    responses = []
    for e164, nid in POOL.items():
        # a near miss first, so a prefix match would pick the wrong id
        responses.append({"data": [{"id": "near-miss", "number": e164 + "9"},
                                   {"id": nid, "number": e164}]})
    responses.append({"id": GID, "name": "repair-updates", "sticky_sender": True,
                      "phone_number_count": 0})
    for e164, nid in POOL.items():
        responses.append({"id": f"m-{nid[-1]}", "number_group_id": GID, "phone_number": e164})
    responses += [{"sid": "msg-1", "status": "queued"}, {"sid": "msg-2", "status": "queued"}]
    rec = V.Recorder(responses=responses)
    for ns in (recipe.client.number_groups, recipe.client.phone_numbers,
               recipe.client.compat.messages):
        ns._http = rec

    group_id = recipe.create_pool("repair-updates", list(POOL))
    assert group_id == GID
    recipe.send(group_id, TO, "Your bike is ready.")
    recipe.send(group_id, TO, "Reminder: your bike is ready.")

    memberships = f"{GROUPS}/{GID}/number_group_memberships"
    # every lookup before the group exists, then the group, then the memberships
    expected = [("GET", NUMBERS)] * len(POOL) + [("POST", GROUPS)]
    expected += [("POST", memberships)] * len(POOL) + [("POST", MESSAGES), ("POST", MESSAGES)]
    assert [(c["method"], c["path"]) for c in rec.calls] == expected, \
        [(c["method"], c["path"]) for c in rec.calls]

    lookups, create, adds = rec.calls[:len(POOL)], rec.calls[len(POOL)], rec.calls[len(POOL) + 1:-2]
    first, second = rec.calls[-2:]
    assert create["body"] == {"name": "repair-updates", "sticky_sender": True}, create
    for (e164, nid), lookup, add in zip(POOL.items(), lookups, adds):
        assert lookup["params"] == {"filter_number": e164}, lookup
        assert add["body"] == {"phone_number_id": nid}, add
    assert first["body"] == {"To": TO, "Body": "Your bike is ready.",
                             "MessagingServiceSid": GID}, first
    assert second["body"] == {"To": TO, "Body": "Reminder: your bike is ready.",
                              "MessagingServiceSid": GID}, second

    # the spec's word on each request
    spec = V.spec("rest")
    V.assert_documented("rest", "POST", GROUPS, create["body"])
    V.assert_documented("rest", "POST", f"{GROUPS}/{{NumberGroupId}}/number_group_memberships",
                        adds[0]["body"])
    V.assert_documented("rest", "GET", NUMBERS, None, lookups[0]["params"])
    V.assert_documented("compat", "POST", first["path"], first["body"])
    assert body_schema(spec, GROUPS)["required"] == ["name"]
    sticky = deref(spec, body_schema(spec, GROUPS)["properties"]["sticky_sender"])
    assert (sticky["type"], sticky["default"]) == ("boolean", False), sticky
    assert sticky["description"] == ("Whether the number group uses the same 'From' number for "
                                     "outbound requests to a number, or chooses a random one."), \
        sticky["description"]
    member = body_schema(spec, f"{GROUPS}/{{NumberGroupId}}/number_group_memberships")
    assert member["required"] == ["phone_number_id"], member["required"]

    compat = V.spec("compat")
    msg = body_schema(compat, "/Accounts/{AccountSid}/Messages")
    assert msg["required"] == ["To"], msg["required"]
    assert "MessagingServiceSid" in msg["properties"], sorted(msg["properties"])
    assert "Either `From` or `MessagingServiceSid` must be provided" in \
        deref(compat, msg["properties"]["From"])["description"]

    print(f"ok: POST {GROUPS} sticky_sender=true, {len(POOL)} lookups and memberships, then "
          f"two compat sends to {TO} naming MessagingServiceSid={GID[:8]}... with no From")


if __name__ == "__main__":
    main()
