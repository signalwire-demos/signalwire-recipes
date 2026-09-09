# Write a reusable AI agent skill

> One class carries the tools, the hints and the prompt, and any agent adds it
> in a line.

**Scenario:** a bike shop and its workshop, each with their own hours

## What this demonstrates

A skill is a unit, not a helper function. `StoreHoursSkill` brings everything an agent
needs to answer questions about opening times. That is the tool, the recogniser hints,
and the prompt sections telling the model when to use it. The agent that
wants it writes one line.

The same class is added twice here with different `params`, so one skill serves
two locations without being copied.

## How it works

A `SkillBase` subclass declares a name and fills in three contributions.

```python
class StoreHoursSkill(SkillBase):
    SKILL_NAME = "store_hours"
    SUPPORTS_MULTIPLE_INSTANCES = True

    def setup(self):        # validated before the agent is served
    def get_hints(self):    # words the recogniser would guess at
    def _get_prompt_sections(self):   # what the model is told
    def register_tools(self):         # the tools themselves
```

`setup()` returns a boolean, and returning `False` stops the skill loading. A
skill that cannot work should say so at startup rather than mid-call.

`register_tools` uses `self.define_tool`, not `self.agent.define_tool`. The
wrapper merges the skill's `swaig_fields` into every tool it registers, which
is how a caller of the skill sets things like `secure` once for all of them.

To make your own class addressable by name, register it:

```python
skill_registry.register_skill(StoreHoursSkill)
agent.add_skill("store_hours", {"tool_name": "shop_hours", ...})
```

`add_skill_directory()` is the other route, for a directory of skills laid out
like the built-in ones.

The multi-instance rule is worth reading twice. The instance key is
`SKILL_NAME` plus `params["tool_name"]`, so two instances need distinct tool
names. Add the same skill twice without them and the second is dropped with a
warning in the log and no error anywhere. The tool the model sees is named from
the same value, which is also what stops the two tools colliding.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

Point a phone number's SWML webhook at
`https://<user>:<password>@<your-host>/shop/`, using the credentials you set.

## Verify it

No network, no account:

```bash
python verify.py          # from the recipe folder, not python/
```

It registers the class, builds the agent and asserts:

- the class is retrievable from the registry under its `SKILL_NAME`
- both instances reach the SWML as `shop_hours` and `workshop_hours`, each
  describing its own location
- the skill's hints and both prompt sections are in the document
- `params` reach the handler: Saturday is open at the shop and closed at the
  workshop
- an unknown day returns `UNKNOWN_DAY` and no real opening time
- an agent adding the skill twice without `tool_name` ends up with one tool

## Limitations

Skills compose tools, not conversations. Two skills that both want to own the
greeting will fight over the prompt, and nothing arbitrates that for you.

`SUPPORTS_MULTIPLE_INSTANCES` is opt-in and defaults to false. A skill written
without it cannot be added twice, and the failure is a log line.

## What to change first

Drop `tool_name` from both `add_skill` calls and run the verifier. One tool
survives, the workshop is gone, and nothing raised.
