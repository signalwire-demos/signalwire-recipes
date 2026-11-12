# AI package tracking line: an external API called from the SWML with no server in the call path

> A package tracking demo built to show a voice AI agent calling a carrier API without a backend. The HTTP request and the sentence template ship inside the SWML, and SignalWire runs them during the call.

**Scenario:** A caller reads out a tracking number and hears where the package is, fetched from a carrier feed during the call

## What this demonstrates

An external API called with no backend. `track_package` is a DataMap tool. The
HTTP GET, the template that turns the JSON into a sentence, and the not-found
fallback are declared in `app.py` and shipped inside the SWML. SignalWire's
servers run them during the call. There is no Python handler and no `/swaig`
webhook for this tool, so nothing on this server runs while the caller waits.
The model sees the finished sentence and never the raw response or the API key.

The agent asks for a tracking number, reads it back to confirm, and looks it
up. The caller hears the status (in transit, delivered, or an exception), the
details, and where and when the package was last scanned. A number that is not
found gets a request to read it again.

## How it works

`DataMap(...).webhook("GET", url)` declares the request, `.output(...)` the
sentence template, `.fallback_output(...)` the line for an unreachable feed and
`.error_keys(...)` the fields that mean not found.
`register_swaig_function(datamap.to_swaig_function())` puts it on the agent.
The tests prove the shape from the dumped SWML. The function carries a
`data_map` and no `web_hook_url`, no handler is registered, and the SDK refuses
to run it locally. The same block pasted into any SWML script's `ai` verb works
with no server at all.

One template rule: in a webhook's `output` the platform reads the JSON response
from the root (`${status}`, not `${response.status}`), and the arguments are
`${input.args.x}`. In the URL and the top-level fallback `output`, the
arguments are `${args.x}`.

Where each mechanism lives in the repository:

- `DataMap(...).webhook("GET", url)`: `app.py`, `build_track_package`
- `.output(...)`, `.fallback_output(...)` and `.error_keys(...)`: `build_track_package`, templates in `config.py`
- `register_swaig_function(datamap.to_swaig_function())`: `TrackingAgent.__init__`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a mock carrier feed. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The app only serves SWML and keeps no state, so `agent.run()` deploys
unchanged to AWS Lambda or Google Cloud Functions. Or skip the app and put the
SWML in a Dashboard script.

A DataMap runs on SignalWire's servers, so `TRACKING_API_KEY` ships in plain
text in every SWML document this app serves. Anyone who can fetch the SWML can
read it, and it can appear in call and SWML logs. Use a read-only key scoped to
tracking lookups, and rotate it if the basic-auth password leaks. If the key
can do more than read, use a webhook tool that holds it on the server.

## What to change first

Open `config.py`: point `TRACKING_URL` at your carrier, or set
`TRACKING_API_URL` and `TRACKING_API_KEY` in `.env`, then rewrite
`OUTPUT_TEMPLATE` with the field names your carrier's JSON uses. `COMPANY_NAME`
and `VOICE` set the greeting.
