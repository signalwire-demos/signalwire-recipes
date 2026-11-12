# AI website chat agent: the phone agent in a chat bubble, with the API token kept off the page

> A website chat demo built to show channel parity from the browser. A ChatGateway holds the API token, pins the agent URL and caps conversations, so the page carries only a publishable key.

**Scenario:** A hotel guest opens the chat bubble on the website and gets the same concierge, with the same rules, that answers the phone

## What this demonstrates

Channel parity from the browser rather than the phone. `concierge.py` is the
whole agent (prompt, steps, tools), the same file the SMS concierge ships, and
has no channel code. The voice call fetches its SWML at `/`. The widget talks
to a `ChatGateway` mounted at `/chat`, which passes that same URL to the AI
Chat service as `config_url`. A web visitor runs the identical steps and
tools. `verify` exposes only `verify_guest` with `valid_steps=[]`, and only its
handler opens `concierge`. `request_service` files for the room in
`global_data.guest`, and the model never passes a room.

`web/` is a sample static hotel site with a chat widget in the corner. The
widget opens with the concierge's greeting, asks for the room number and last
name, then answers amenity questions and logs service requests to
`data/requests.json`. A reload resumes the conversation. Calling the voice
number reaches the identical agent.

## How it works

The browser holds only a publishable key. The gateway keeps the API token and
pins `config_url`, so a page cannot point the key at another agent. It filters
the system prompt and tool traffic out of the transcript, and caps new
conversations and turns from `config.py`. The widget speaks three calls,
`start`, `chat` and `log`, carrying an `X-Chat-Handle` the gateway issued.
`CHAT_ALLOWED_ORIGINS` lists the sites that may embed it.

Where each mechanism lives in the repository:

- `define_contexts`, `set_functions` and `set_valid_steps([])`: `concierge.py`, `HotelConcierge.__init__`
- `update_global_data` then `swml_change_step`: `concierge.py`, `verify_guest`
- `ChatGateway(config_url=..., key=..., allowed_origins=...)`: `app.py`, `build_gateway`
- `agent.mount(gateway.router(), prefix="/chat")`: `app.py`, `WebConcierge.__init__`
- the widget's `start`, `chat` and `log` calls with `X-Chat-Handle`: `web/widget.js`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a sample site under
`web/`. It pins `signalwire-sdk` 3.7.5, ahead of the
3.0.1 the recipes here are verified against. Its claims are proven by its own
tests, not by a verifier in this repository. The repository carries no licence
file at the time of writing, which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

Requests are appended to a local JSON file, so it is not suited to serverless
as shipped. The caps are per process: run one replica, or set
`SIGNALWIRE_CHAT_GATEWAY_SECRET` on all of them. The platform calls your tools
over the tunnel, so web chat needs the public URL even when the page is on
localhost. The recipe `put-an-agent-in-a-web-chat-widget` is the verified
3.0.1 version, with the gateway built by hand on the documented wire.

## What to change first

Open `config.py`: `WIDGET` sets the widget's placement (`position`) and
branding (`title`, `color`), `ALLOWED_ORIGINS` and `CHAT_ALLOWED_ORIGINS` list
the sites that may embed it, and `SERVICES` is the tool set. The agent itself
is in `concierge.py`; change it there and voice and web chat change together.
