# Issue a browser calling token restricted to chosen destinations

> The token is the permission. A visitor holding one can reach the list and
> nothing else.

**Scenario:** a "call us" button on a marketing site

## What this demonstrates

A browser can place a call without an account, and without being able to dial
anything you did not authorise. `allowed_addresses` on a guest token is the
whole of its reach.

The browser chooses a key into a server-authored table. It cannot add an address, so
the worst a visitor can do is pick another page's desks. Every address behind any key
is effectively public to every visitor.

## How it works

The POST to `/api/fabric/guests/tokens` carries `allowed_addresses`, the only
required field in the body.

```python
client.fabric.tokens.create_guest_token(
    allowed_addresses=DESKS[page],
    expire_at=int(time.time()) + TOKEN_TTL_SECONDS,
)
```

The browser posts which page it is on, and the server ignores any address it sends.
That distinction is the recipe. A value the browser supplies is a value the browser
can change, so it may select from the table but never add to it. Keys are guessable,
so treat every desk in the table as reachable from every page.

An unknown page mints nothing at all. A token with an empty list dials nothing, which
looks exactly like a broken button and is harder to diagnose than a 404.

The documented maximum is ten addresses, and the code checks its own table
against that rather than discovering it on a live request.

`expire_at` keeps the window short. A page reload mints another, so there is
no reason for one to live long.

The response carries the minted token and nothing else. The project ID and API
token stay on the server, which is the point of having a server in this flow at
all.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # add your credentials
python app.py
```

The browser side is `call-from-a-browser`, with this `/token` route in place of
the subscriber one.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer replaced by a recorder, the verifier asserts:

- one documented POST to `/api/fabric/guests/tokens`, checked against
  `tools/openapi/rest.json`
- `allowed_addresses` is exactly the list for that page, and a page offering
  two desks gets both
- the list is within the documented maximum, and an expiry is set
- a request that also sends `allowed_addresses` and `address` changes nothing
  about what is minted
- three kinds of unknown page return 404 and make no request at all
- neither the API token nor the project ID appears in any response

## Limitations

A guest token is bearer authority. Anyone with a copy has the reach of the visitor it
was minted for, until it expires. That is what the short TTL is for.

The addresses are a static table here. Deciding them per visitor means
authenticating the visitor, at which point a Subscriber token is the better
fit.

## What to change first

Add a desk to the `DESKS` table and give a page two entries instead of one. Keep
`allowed_addresses` coming from that table: the moment it comes from the request body,
the page can dial anything on your account.
