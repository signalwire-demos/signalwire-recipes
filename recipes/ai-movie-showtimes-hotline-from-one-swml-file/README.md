# AI movie showtimes hotline: a governed voice agent in one SWML file and no server

> A movie showtimes demo built to show a voice AI agent as one SWML file pasted into the Dashboard. Its only tool is a DataMap that fetches a feed, so the model never sees a URL it was not given.

**Scenario:** A caller asks what is playing tonight and hears the films and times from a JSON feed, with nothing installed anywhere

## What this demonstrates

Governance without code. The agent is one SWML file, `showtimes.swml.yaml`,
pasted into the Dashboard or created with one REST call. Its only tool is a
`data_map` that runs on SignalWire. It fetches your feed, builds the sentence
the model reads with a `foreach` over `films`, and swaps in fixed lines when
the feed is empty (`expressions`) or unreachable (`output`). The model never
sees the raw feed, cannot call a URL you did not list, and has no other tool.
Nothing in the file points at a server you run.

The caller rings the theater's number and asks, for example, "When is Orbit of
Nine playing?". The AI calls `get_showtimes`, and SignalWire's servers fetch
`data/showtimes.json` and turn it into one sentence per film. The agent reads
back the times for that film, or the whole list.

## How it works

The `ai` verb carries an inline prompt and one SWAIG function whose
`data_map.webhooks` entry GETs the feed. Inside a webhook's `foreach`,
`expressions` and `output`, the response's fields are read from the root
(`${films}`, `${listing}`), not as `${response.films}`; the tests check this
against the SDK's DataMap simulator. Changing the showtimes means editing the
feed, and callers hear the new times on the next call with no redeploy.

Where each mechanism lives in the repository:

- the `ai` verb with an inline prompt: `showtimes.swml.yaml`, `sections.main[1]`
- `data_map.webhooks`, the GET: function `get_showtimes`
- `foreach`, one sentence per film: the webhook's `foreach`
- `expressions`, the empty-feed line: the webhook's `expressions`
- the top-level `output`, the fallback: `get_showtimes.data_map.output`

## Limitations

This is one SWML file in another repository, with pytest tests beside it that
need Python only to run. Its claims are proven by those tests, not by a
verifier here. The repository carries no licence file at the time of writing,
which is its owner's to add.

The feed must be a public HTTPS URL; the default is the repository's own
`data/showtimes.json` on GitHub raw. The recipe
`run-an-agent-from-one-yaml-file` is the Agents SDK twin of this file.

## What to change first

There is no `config.py`: the knobs are in `showtimes.swml.yaml`. Change the
theater name in the prompt (`Starlight Cinema`) and the feed URL in
`get_showtimes.data_map.webhooks[0].url`. Each film needs `title`, `rating`,
`runtime` and `times`, as in `data/showtimes.json`.
