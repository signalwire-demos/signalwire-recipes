"""Ground an agent in your docs.

`search_docs` is a SWAIG tool that queries Datasphere - SignalWire's hosted
document store with chunking and vector search - restricted to the documents
tagged for this agent. The model receives matching passages, and nothing else.

Upload documents (PDF, DOCX, Markdown, ...) in the Dashboard under Datasphere,
or with `POST /api/datasphere/documents`, and tag them; the tag is the corpus
boundary here.

Written against signalwire-sdk 3.0.1 (RestClient.datasphere).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

CORPUS_TAGS = os.getenv("DATASPHERE_TAGS", "product-docs").split(",")
TOP_K = int(os.getenv("DATASPHERE_COUNT", "3"))


def search(client, query, tags=CORPUS_TAGS, count=TOP_K):
    """Return the matching passages, most relevant first."""
    res = client.datasphere.documents.search(query_string=query, tags=tags, count=count)
    return [c.get("text") or c.get("content", "") for c in res.get("chunks", [])]


class DocsAgent(AgentBase):
    def __init__(self, client=None):
        super().__init__(name="docs", route="/docs")
        self.client = client or RestClient()
        self.prompt_add_section(
            "Role",
            "You answer questions about our product from the documentation. For "
            "every question, call search_docs first and answer from the passages "
            "it returns. If nothing relevant comes back, say the documentation "
            "does not cover it.",
        )

    @AgentBase.tool(
        name="search_docs",
        description="Search the product documentation for passages on a question",
        parameters={"query": {"type": "string",
                              "description": "What the caller wants to know"}},
    )
    def search_docs(self, args, raw_data):
        query = (args.get("query") or "").strip()
        if not query:
            return FunctionResult("I need a question to search for.")
        passages = search(self.client, query)
        if not passages:
            return FunctionResult("No relevant documentation was found for that.")
        body = "\n\n".join(f"- {p}" for p in passages)
        return FunctionResult("Relevant documentation:\n\n" + body)


if __name__ == "__main__":
    DocsAgent().serve(port=int(os.getenv("PORT", "8080")))
