# Keep per-call state server-side, keyed by call id

> Per-call state lives server-side keyed by `call_id`. Only a count and the distinct areas go to `global_data`, and the handlers read the full record from the store.

**Scenario:** a mechanic phoning in a bike inspection, one finding at a time

## What this demonstrates

`global_data` travels with every tool call and the model can see it. That makes
it the right place for a short, AI-facing summary and the wrong place for a
growing record. You keep the record in a store keyed by `call_id`, which the
platform posts with every tool call. You write only a count and the distinct
areas to `global_data`. A second tool reads the whole record back from the
store when the mechanic asks for it.

## How it works

```python
def record_finding(self, args, raw_data):
    call_id = raw_data.get("call_id")
    findings = STORE.setdefault(call_id, [])
    findings.append({"area": area, "detail": detail})          # the full text
    seen = list(dict.fromkeys(f["area"] for f in findings))    # distinct areas
    r = FunctionResult(f"Recorded {area}. {len(findings)} findings so far.")
    r.add_action("set_global_data", {                          # the summary
        "findings": len(findings), "areas": ", ".join(seen)})
    return r
```

After the third finding, what the platform receives:

```json
{"response": "Recorded wheels. 3 findings so far.",
 "action": [{"set_global_data": {"findings": 3, "areas": "brakes, gears, wheels"}}]}
```

The three findings in the store run to several hundred bytes; the whole
`action` stays under 120. Because `areas` holds distinct values, twenty more
findings on one area leave it the same size. `read_back_report` reads
`STORE[call_id]`, not `global_data`. `global_data` never carries the full text
between turns; the model receives it in the read-back response.

`call_id` is the key because it is the one identifier the platform attaches to
every tool call for the life of the call. Two distinct call ids get two
records.

## Run it

```bash
cd python
pip install -r requirements.txt
cp ../.env.example .env          # set SWML_BASIC_AUTH_PASSWORD
python app.py
```

The webhook needs a public HTTPS URL. For a local run, expose port 3000 with a
tunnel such as ngrok and use that hostname. Point a number's SWML webhook at
`https://<user>:<password>@<your-host>/inspection/`, report three findings at
length, then ask for the report.

## Verify it

No network, no account.

```bash
python verify.py          # from the recipe folder, not python/
```

The verifier runs the handlers with the platform's payload shape and asserts
the following.

- both tools render, and `area` carries the five areas as an `enum`
- for each of three long findings on one call, the whole `action` list is 120 bytes of JSON or fewer
- none of those actions contains the detail text
- each of those actions is exactly `set_global_data` with the count and the distinct areas, and the response tells the model the count
- the store for that call holds the full text, more than three times the cap
- a finding on a second call gets its own record, and the first call's record is byte-for-byte unchanged
- twenty more findings on one area leave the action under the cap with the count at 21
- `read_back_report` returns every detail from the store for its own call, with no action, and `INCOMPLETE` for a call with none
- an invalid finding leaves the whole store byte-for-byte unchanged

## Limitations

The store is a dictionary in the process. A restart loses it, and two replicas
would not share it; your version is a table keyed by `call_id`.

Nothing here removes a call's record when the call ends. Where you do that is
your design choice; the store only grows in this recipe.

## What to change first

Put `detail` into the `set_global_data` action and run the verifier. It fails
on the first finding, at the size check. That is the point: the record was
about to ride along with every tool call for the rest of the conversation.
