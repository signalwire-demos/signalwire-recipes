# AI SMS concierge: one agent definition answering texts and calls with the same rules

> An SMS concierge demo built to show one agent file serving voice and text. Inbound texts run the same SWML through the AI Chat API, so verification, step-scoped tools and the service enum hold on both channels.

**Scenario:** A hotel guest calls or texts the same concierge, verifies a room, asks about amenities and logs requests, with one conversation per phone number

## What this demonstrates

One agent definition serves more than one channel. `concierge.py` holds the
whole agent (prompt, steps, tools) and knows nothing about phones or SMS. A
voice call fetches its SWML from `/`. An inbound text goes to `/sms`, which
calls `AIChatClient.chat()` with that same URL as `config_url`, so the AI Chat
service runs the identical SWML. The governance comes with it on both
channels. In `verify`, `verify_guest` is the only tool and `valid_steps=[]`, so
only its handler opens `concierge`. `request_service` files for the room in
`global_data.guest`, so the model never passes a room number. And `service` is
an enum of `config.SERVICES`, which the handler refuses to exceed.

The concierge asks for the guest's room number and last name, checks them
against `data/guests.json`, then answers amenity questions and logs service
requests to `data/requests.json`. Guests can call the voice number or text the
SMS number. A texting guest keeps one conversation per phone number, so "and
the gym?" an hour later still knows who they are.

## How it works

`/sms` accepts both inbound payload formats, checks
`validate_webhook_signature`, and renders the reply as the messaging SWML the
platform expects. Texts from the SMS number itself get no reply, so the agent
cannot loop on its own answers. The AI Chat API needs the project token's Chat
scope, as well as Voice and Messaging. The agent's tools are called over it
exactly as on a voice call, with `conversation_type: chat`.

Where each mechanism lives in the repository:

- `define_contexts`, `set_functions` and `set_valid_steps([])`: `concierge.py`, `HotelConcierge.__init__`
- `update_global_data` then `swml_change_step`: `concierge.py`, `verify_guest`
- the room from `global_data`, never from arguments: `concierge.py`, `request_service`
- `AIChatClient.chat(conversation_id, message, config_url=...)`: `app.py`, `SmsConcierge.answer`
- inbound SMS, both payload formats: `app.py`, `parse_inbound` and `render_reply`
- `validate_webhook_signature`, required: `app.py`, `sms_router`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and mock hotel data under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

Service requests are appended to a local JSON file; move `REQUESTS_FILE` to a
database before running serverless. The SMS number must be on a 10DLC campaign
or verified toll-free, or carriers reject its texts. The author verified the
`/sms` to AI Chat path with simulated webhook POSTs and a delivered reply. A
handset texting the number end to end is still to be tested. The recipe
`run-the-same-agent-over-text` is the verified 3.0.1 version of the AI Chat
mechanism.

## What to change first

Open `config.py`: change `SERVICES` (the tool set, which requests the
concierge may log) and `HOTEL_NAME`, then point `GUESTS_FILE` and
`AMENITIES_FILE` at your own data. The agent itself is in `concierge.py`;
anything you change there applies to voice and SMS at once.
