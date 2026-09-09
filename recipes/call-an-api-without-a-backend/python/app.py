"""Call an API without a backend.

A DataMap tool is executed by SignalWire, not by you. The HTTP request, the
response templating and the error handling all travel inside the SWML document,
so there is no webhook of yours for the platform to call back to.

This one looks a book up by ISBN against Open Library, which needs no API key,
so the recipe runs as written.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, DataMap, FunctionResult

# the SDK does not read .env for you
load_dotenv()


def book_lookup():
    """A tool with no handler. The platform performs the call."""
    return (
        DataMap("look_up_book")
        .purpose(
            "Look up a book by its ISBN to confirm the title before ordering. "
            "Use this whenever the caller reads out an ISBN."
        )
        .parameter(
            "isbn", "string",
            "The 10 or 13 digit ISBN, digits only, no dashes.",
            required=True,
        )
        # ${args.x} is substituted into the URL before the platform sends it
        .webhook("GET", "https://openlibrary.org/isbn/${args.isbn}.json")
        # ${response.x} reads the parsed JSON body. This output belongs to the
        # webhook above it.
        .output(FunctionResult(
            "ISBN ${args.isbn} is ${response.title}, published "
            "${response.publish_date}."
        ))
        # a body carrying this key means the lookup failed
        .error_keys(["error"])
        # top-level: spoken only when every webhook above has failed
        .fallback_output(FunctionResult(
            "I could not reach the book catalogue. Ask the caller to read the "
            "ISBN again, or offer to take the title instead."
        ))
    )


class CatalogueAgent(AgentBase):
    def __init__(self):
        super().__init__(name="catalogue", route="/catalogue")
        self.prompt_add_section(
            "Role",
            "You take book orders for an independent bookshop. Confirm the "
            "title with the lookup tool before you add anything to an order.",
        )
        # a DataMap is registered as a raw function definition
        self.register_swaig_function(book_lookup().to_swaig_function())


agent = CatalogueAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
