# Voice AI latency lab: the same agent under several models and voices, timed from the platform's own stamps

> A latency lab demo built to show model choice as a configuration change, measured from the platform's per-turn timings. A test diffs every configuration's SWML against the baseline so a comparison cannot quietly become unfair.

**Scenario:** A harness calls one agent under each configuration with the same scripted caller and prints a side-by-side latency table

## What this demonstrates

Model choice is a configuration change, not a code change. The dynamic config
callback picks a configuration from a server-side whitelist and changes
exactly two things: the LLM model (`set_prompt_llm_params(model=...)`) and the
TTS voice (`add_language(...)`). An unknown `?config=` gets the default, and a
model name in the URL is never used. Everything else is identical: the prompt,
the one step with its one tool `check_hours`, `valid_steps=[]`, the
temperature. A test diffs the SWML of every configuration against the baseline
and fails if anything other than the model and voice differs. A comparison
cannot quietly become unfair. Timings come from the platform's data, never
from the model.

`app.py` is a small store-hours agent: the caller asks about opening hours,
the agent calls `check_hours` and answers in one sentence. A query parameter
such as `?config=nano-rime` picks one entry from `CONFIGS` in `config.py`.
`run_lab.py` places scripted calls round-robin across the configurations, one
number dialling the other and speaking the same three lines each time. After
each call the platform POSTs its post-prompt report, and `on_summary` files it
under the configuration named in `global_data`. The lab turns the reports into
a comparison table of median and 95th percentile per latency segment.

## How it works

The numbers come from the post-prompt payload (`raw_call_log`, falling back to
`call_log`). Each `assistant` entry carries `stamps_us`, microsecond wall-clock
stamps for `last_word_end`, `status_pushed`, `request_detect`, `first_token`,
`first_utterance` and `first_audio`, and the reported `eos_to_push_latency`,
`latency`, `utterance_latency`, `audio_latency` and `acoustic_latency` fields.
Mouth-to-ear is `first_audio - last_word_end`; turn detection is
`eos_to_push_latency`; the model's share is `latency`; the rest splits into
utterance assembly and TTS. There is one value per caller turn, and entries
sharing a `last_word_end` anchor count once. An entry without both stamps is
counted as untimed rather than estimated, and percentiles are nearest-rank.
Calls are interleaved across configurations so drift over time hits every
configuration equally. The caller is synthetic TTS over PSTN, so every
configuration hears identical audio. On the author's lab calls the computed
mouth-to-ear matched the platform's own `acoustic_latency` to within a
millisecond.

Where each mechanism lives in the repository:

- `set_dynamic_config_callback` with the whitelist: `app.py`, `configure()` and `pick_config()`
- `set_prompt_llm_params(model=..., temperature=...)`: `configure()`
- `add_language`, the voice under test: `configure()`
- `set_post_prompt` and `on_summary`, the timing payload capture: `LatencyLabAgent`
- `set_functions` and `set_valid_steps([])`: step `answer`
- the timing parser and report: `lab/timings.py`, `lab/report.py`
- the scripted caller: `run_lab.py`, with the upstream repository's `scripts/smoke_call.py`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and a lab harness. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

Its author marks it `confirm`: built and tested offline, with parts not yet
confirmed on a live call.

These are server-side stamps and do not include the PSTN transport to and
from the caller's handset. Nothing yet confirms that this method matches how
SignalWire measures latency publicly: which anchor, which percentile, whether
filler audio counts. Treat the table as a relative comparison between
configurations, not a publishable figure. The lab needs two numbers on the
Space and repoints the agent number's handler for each call. The models and
voices in `CONFIGS` must be enabled on your Space. The payloads are written to
the local `data/runtime/runs`, so serverless is a poor fit. The recipe
`measure-voice-ai-latency` is the planned verified version of this
measurement.

## What to change first

Open `config.py` and edit `CONFIGS`, the configuration matrix: one entry per
model and voice pair, with the first entry as your baseline. An optional
`known_issue` string on an entry is printed under the report table and never
reaches the SWML. Then set `CALLER_SCRIPT` to lines that match your real
calls; a tool-heavy turn and a chit-chat turn measure different things.
`CALLER_PAUSE_SECS` gives the agent time to answer.
