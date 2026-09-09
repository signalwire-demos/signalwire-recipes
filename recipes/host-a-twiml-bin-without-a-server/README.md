# Host a TwiML bin without a server

> One POST stores a cXML document on SignalWire and returns the URL it is served from; a lookup and one more POST put a phone number on it. The call never touches a server of yours.

**Scenario:** a shop's main line greets the caller and forwards to the workshop

## What this demonstrates

A small cXML application, a `Say` and a `Dial`, does not need hosting.
`POST /api/fabric/resources/cxml_scripts` takes `display_name` and `contents`,
the only two fields the spec requires, and answers with a resource whose
`cxml_script.request_url` is where SignalWire serves it. `POST
/api/fabric/resources/{id}/phone_routes` with `handler: calling` then routes a
number you own to it, by the number's resource id, which is what the lookup in
between is for.

That is the Fabric form of a TwiML bin. The compat form is the same idea
under the Twilio-shaped path: `POST /api/laml/2010-04-01/Accounts/<project>/LamlBins`
with `Name` and `Contents`, which the verifier checks the compat spec still
documents.

## How it works

```python
CONTENTS = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<Response>\n'
            '  <Say>Connecting you to the workshop.</Say>\n'
            '  <Dial timeout="20">{to}</Dial>\n'
            '</Response>\n')

def create():
    made = client.fabric.cxml_scripts.create(display_name=NAME, contents=contents())
    return made["id"], made["cxml_script"]["request_url"]

def point_number(script_id, e164):
    return client.fabric.resources.assign_phone_route(
        script_id, phone_route_id=number_id(e164), handler="calling")
```

The [Dial reference](https://signalwire.com/docs/compatibility-api/cxml/reference/voice/dial.md)
gives `timeout` a default of 30 seconds; this document sets 20. It takes a bare
phone number as its content. The `Say` runs first, so the caller hears
something before the ring.

`number_id` is the reason `point` takes a lookup. The spec describes
`filter_number` as returning "all Phone Numbers containing this value". The
listing for `+15551230000` therefore carries longer numbers that contain it,
and the helper compares exactly before it binds anything.

Hosted scripts can be templated. The
[Mustache guide](https://signalwire.com/docs/compatibility-api/guides/mustache-templates.md)
gives `{{AccountSid}}`, `{{From}}` and `{{To}}` to both flavours. It adds
`{{CallSid}}`, `{{CallStatus}}`, `{{Direction}}` and `{{ParentCallSid}}` for
voice, and its voice example forwards with `callerId="{{From}}"`. This document
uses no templating, to keep it to the one claim.

Check one thing before copying that example. The Dial reference says a
`callerId` "must either be verified or purchased in the SignalWire Dashboard".
`forward-calls-to-a-phone-and-keep-the-callers-number` is the SWML recipe for
the same idea.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # project id, API token, space, FORWARD_TO
python app.py create             # prints the script id and its request_url
python app.py point <script_id> +15551230000
```

`point` takes the number you own that should ring the bin, not `FORWARD_TO`,
which is the phone the document dials.

The TypeScript surface is the same requests on `@signalwire/sdk`'s
`RestClient`, on Node 20.18.1 or newer:

```bash
cd typescript
npm ci
cp ../.env.example .env
npm start create
npm start point <script_id> +15551230000
```

Call the number. Nothing of yours is running.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

With the HTTP layer replaced by a recorder, the verifier asserts the following.

- the expected document parses as cXML: `Response` holding a `Say` and a `Dial` with `timeout="20"` to the forwarding number
- the create is a documented POST to `cxml_scripts` whose body is exactly `display_name` and those contents, and the spec requires exactly those two fields
- the helper returns the id and the `request_url` from the response, and the spec documents `request_url` on the resource
- the lookup is a documented GET whose `filter_number` the spec calls a contains match, and the listing answers with a longer neighbour first, so picking the first row would bind the wrong number
- the bind is a documented POST to the script's `phone_routes` with a `handler` from the spec's enum
- a listing without the number raises and sends no bind at all, on both surfaces
- updating the script is a documented PUT of new `contents`
- the compat spec documents `LamlBins` with `Name` required and `Contents`
- the TypeScript surface makes the same three requests with the same bodies

The forwarding number in the verifier is not either surface's default, so a
surface that never read its environment would render a different document.

## Limitations

The verifier proves the requests and the document, not the call. Whether the
platform renders this cXML as expected on a live call is a call to make.

The TypeScript SDK prints a note on `assignPhoneRoute`, preferring its
`phoneNumbers.setCxmlWebhook`, which writes a URL onto the number directly and
skips the resource. This recipe keeps the documented `phone_routes` request
because the hosted resource is the point.

The document is built by string formatting, so a forwarding number carrying an
ampersand or an angle bracket would make it invalid cXML. Phone numbers do
not, but escape the value if you template anything else into it.

Updating the script is `PUT /api/fabric/resources/cxml_scripts/{id}` with new
`contents`; the numbers routed to that resource keep pointing at it.

## What to change first

Replace the `Dial` with `<Redirect>https://your-host/voice</Redirect>` and the
bin becomes the entry point to an application you host, with the number still
bound to the bin. Move the app, and the bin is the one thing you update.
