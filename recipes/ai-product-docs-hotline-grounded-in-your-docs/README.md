# AI product docs hotline: answers taken from your documentation or a refusal, never a guess

> A product docs hotline demo built to show a voice AI agent grounded by its tool rather than its prompt. A similarity gate drops weak search results before the model sees them, so an off-topic question gets a refusal.

**Scenario:** A caller asks how the product works and hears an answer from a local search index of the docs, or "That's not in the docs"

## What this demonstrates

Grounding is enforced by the tool, not requested by the prompt. The agent has
one tool, `search_docs`, the `native_vector_search` skill, and it can read only
`data/knowledge.swsearch`. Before the model sees a result, `grounded_only()`
drops every chunk whose vector similarity is under `SIMILARITY_THRESHOLD`.
When nothing passes, the model gets the fixed marker `NOT_IN_DOCS` instead of
weak matches it could stretch into an answer. The prompt maps that marker to
the refusal line.

The caller asks a question such as "How do I point a phone number at my
agent?". The agent searches a local index of the files in `docs/` and answers
in two or three sentences from what the search returned. A question the docs
do not cover gets "That's not in the docs." and an offer to help with something
else. The index is built with `sw-search` and committed, so a clean clone
answers on its first call.

## How it works

`add_skill("native_vector_search", ...)` registers the tool and points it at
the index file. The skill's `response_format_callback` is where
`grounded_only()` runs, so the gate sits between the search and the model. The
fifteen sample pages in `docs/` are short paraphrases written for the demo;
replace them with your own and run `make index`.

Two details of the 3.7.5 skill the code works around, both commented in
`app.py`. The skill's own `similarity_threshold` drops weak vector hits but
lets keyword-only hits through. "What states do you serve?" once matched the
10DLC page on the word "states", so the gate checks each chunk's
`vector_score` instead. And `skip_prompt` does not stop the skill adding a
prompt section, so the app creates its `Knowledge Search` section first and
the skill appends one line to it.

Where each mechanism lives in the repository:

- `add_skill("native_vector_search", ...)`: `app.py`, `DocsHotline.__init__`
- `response_format_callback`, the threshold gate: `app.py`, `grounded_only()`
- the `sw-search` index build: `Makefile`, target `index`
- `add_language` with function fillers: `app.py`, `DocsHotline.__init__`

## Limitations

This is a clone-and-own application in another repository, not a snippet: a
Python process with a Dockerfile, pytest tests and sample docs. It pins
`signalwire-sdk` 3.7.5, ahead of the 3.0.1 the recipes here are verified
against. Its claims are proven by its own tests, not by a verifier in this
repository. The repository carries no licence file at the time of writing,
which is its owner's to add.

The search dependencies (PyTorch CPU, sentence-transformers) need about 1 GB
of disk. The image bakes in the embedding model, so the container needs no
internet access at call time. Serverless is a poor fit for the same reason: a
large package and a slow cold start. For serverless, run `sw-search` as a
remote search server and set the skill's `remote_url` instead of `index_file`.

## What to change first

Open `config.py`: set `PRODUCT_NAME`, point `DOCS_DIR` at your own docs, then
run `make index` to rebuild `INDEX_FILE`. If good questions come back as "not
in the docs", lower `SIMILARITY_THRESHOLD`; if off-topic questions get
answers, raise it. `swaig-test --exec search_docs` shows what the gate passes.
