# Bilingual AI support line: English and Spanish from one code path, switching mid-sentence

> A bilingual support demo built to show multilingual as configuration rather than a second code path. Each language is one add_language call, and the handlers return language-neutral JSON the model voices in whichever language is live.

**Scenario:** A caller to an internet provider talks in English or Spanish, switches at any point, and gets an outage check or a balance

## What this demonstrates

Multilingual is a few lines of configuration, not a second code path. Each
language is one `add_language()` call with its own voice, speech fillers and
function fillers, driven by one entry in `config.LANGUAGES`, plus a
per-language `next_step` internal filler. The handlers never write sentences.
`lookup_account`, `check_outage` and `get_balance` return language-neutral
JSON, such as `{"outage": true, "restore_eta": "..."}`, that the model voices
in whatever language the call is in, so the same handler serves both
languages.

The agent answers in English and offers Spanish. It asks for the account
number and service ZIP code and verifies them against `data/accounts.json`.
Then it greets the caller by first name and checks for an outage at their
address or reads the balance due. If the caller switches to Spanish, or back,
at any point, the agent switches with them in that language's own voice,
without repeating questions. It ends with a goodbye in the caller's current
language.

## How it works

The tools are still scoped by step. `identify` exposes only `lookup_account`
and has `valid_steps=[]`, so the account tools do not exist until the handler
verifies the caller and calls `swml_change_step("help")`. The handler copies
only `first_name` and `plan` into `global_data`, for the prompt; the internal
risk flag and billing notes never reach the model. It records the verified
account on the server, keyed by `call_id`, and `check_outage` and
`get_balance` read the account only from that record, never from model
arguments or request `global_data`. Failed lookups count on the server per
account number, caller ID and call, across calls, with a lockout after
`MAX_LOOKUP_FAILURES`, so redialing does not reset them.

Where each mechanism lives in the repository:

- `add_language` with a voice and speech and function fillers per language: `app.py`, `__init__`, one call per `config.LANGUAGES` entry
- `add_internal_filler("next_step", code, ...)`: `app.py`, `__init__`, per language
- `set_params({"languages_enabled": True})`: `app.py`, `__init__`
- language-neutral JSON tool results: `app.py`, the `data()` helper every handler uses
- `set_functions` and `set_valid_steps([])`: steps `identify`, `help`, `wrap_up`
- `update_global_data` then `swml_change_step`: the `lookup_account` handler
- the server-side lookup failure count and lockout: `lockout.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and mock accounts under
`data/`. It pins `signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here
are verified against. Its claims are proven by its own tests, not by a
verifier in this repository. The repository carries no licence file at the
time of writing, which is its owner's to add.

The mock data is read-only, but the lookup failure counts and verified calls
are in-process memory. Move them to shared storage before running on Lambda,
Cloud Functions or more than one replica. The voices are Google Cloud voices
that SignalWire hosts. The recipe `switch-language-mid-call` is the verified
3.0.1 version of the mechanism.

## What to change first

Open `config.py`. To add a language, append one dict to `LANGUAGES` (name, ASR
code, voice, speech fillers, function fillers, step fillers). That is one more
`add_language()` call and nothing else changes, because no handler holds any
text. Pick a voice that speaks the language. Then point `ACCOUNTS_FILE` at
your own data, or replace `load_db()` in `app.py` with calls to your billing
and outage systems, keeping the handlers returning data, not sentences.
