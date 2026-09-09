# Switch language mid-call

> One agent, three languages, no transfer.

**Scenario:** the front desk of a hotel in Montreal

## What this demonstrates

A caller opens in French, switches to English halfway through, and the agent
follows without being asked and without the call going anywhere. It is one AI
session throughout: no second agent, no transfer, no routing decision.

Each language has its own voice, so the caller hears a speaker of their
language rather than one accent reading three.

## How it works

Two things, and the second is the one people miss.

Register each language with a code and a voice:

```python
self.add_language("English", "en-US", "rime.spore")
self.add_language("Spanish", "es-ES", "rime.marisol")
self.add_language("French",  "fr-FR", "rime.celeste")
```

Then turn the feature on:

```python
self.set_params({"languages_enabled": True})
```

Without `languages_enabled`, the list is configuration the platform never
reads. The agent renders, the call connects, and it answers everything in the
first voice. Nothing errors, which is what makes it hard to spot.

The first language registered is the one the agent opens in. Order is a
decision, not an accident: put the language most callers use first, because
that is what they hear before anyone has said anything.

The prompt asks the model to follow the caller and not to comment on the
switch. Announcing "I see you're speaking French now" is the tell that turns a
capability into a party trick.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at
`https://<user>:<password>@<your-host>/frontdesk/`, using the credentials you set.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It renders the SWML and asserts:

- `languages_enabled` is on, so the list is read rather than ignored
- all three languages reach the platform, in registration order
- each carries its own code and voice, and no two are identical
- the document contains no `transfer` and no `connect`, so the switch happens
  inside one session
- the prompt mentions language, so the model knows to follow the caller
- the hand-written SWML surface satisfies the same checks, in the same order

## Limitations

Recognition and synthesis are per language, but the prompt is not. One prompt
serves every language, so anything you write in English is being translated by
the model on the way out.

A voice per language means a voice you have to pick per language. A missing or
wrong voice name does not fail loudly; it falls back, and the caller hears the
wrong accent.

## What to change first

Delete the `languages_enabled` parameter and call in Spanish. The agent
understands and answers in English, which is the failure this recipe exists to
name.
