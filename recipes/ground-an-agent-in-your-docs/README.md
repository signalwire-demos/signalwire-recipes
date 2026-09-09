# Ground a voice AI agent in your documents

> A Datasphere tool searches only the selected tagged corpus and returns the matching passages to the agent.

**Scenario:** a product documentation hotline

## What this demonstrates

Datasphere is SignalWire's hosted document store: upload PDFs, Word files or
Markdown, it chunks and embeds them, and `POST /api/datasphere/documents/search`
returns the passages closest to a query. This agent has one tool,
`search_docs`, which runs that search restricted to the documents tagged for it
and hands the passages back as the tool's response. The retrieval is the
platform's; the boundary is the tag; the code is thirty lines.

What this does *not* prove: that the model will never answer from its own
knowledge. Search evidence cannot enforce a behavioural guarantee; the prompt
asks for it and the tool makes it the path of least resistance. Structural constraints on what the
model can *do* are the governance recipes (`scope-tools-per-step`,
`require-verification-before-unlocking-tools`).

## How it works

```python
res = client.datasphere.documents.search(query_string=query, tags=["product-docs"], count=3)
passages = [c["text"] for c in res["chunks"]]
return FunctionResult("Relevant documentation:\n\n" + "\n\n".join(f"- {p}" for p in passages))
```

The request body (`query_string`, `tags`, `count`, and also `distance`,
`language`, `pos_to_expand`, `max_synonyms`) is the documented Datasphere
search API; `tags` is what scopes the corpus. An empty result returns an
explicit "not covered" response rather than nothing, so the model has something
truthful to say.

Alternatives with the same shape: the SDK's `datasphere` skill (webhook) or
`datasphere_serverless` skill (a DataMap, no server of yours), and
`native_vector_search` for a local `.swsearch` index with no hosted store.

## Run it

1. In the Dashboard, open Datasphere, upload your documents and tag them
   `product-docs` (or set `DATASPHERE_TAGS`).
2. ```bash
   cd python
   pip install -r requirements.txt
   SIGNALWIRE_SPACE=... SIGNALWIRE_PROJECT_ID=... SIGNALWIRE_API_TOKEN=... python app.py
   ```
3. Point a phone number's SWML webhook at `https://<user>:<password>@<your-host>/docs/`, using the credentials from your `.env`.

## Verify it

```bash
python verify.py          # from the recipe folder, not python/
```

It replaces the REST client's HTTP layer with a recorder and runs the tool. The
verifier then asserts:

- one POST to `/api/datasphere/documents/search`
- a body that is a documented search request carrying exactly the corpus tags,
  checked against `tools/openapi/rest.json`
- the response text is the returned passages
- an empty result says so

## What to change first

Give two agents two tags over one Datasphere project, a sales corpus and a
support corpus, and confirm neither can retrieve the other's documents.
