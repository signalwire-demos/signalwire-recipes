"""Cover tool latency with fillers.

A tool that takes two seconds leaves two seconds of silence unless the
document says otherwise. Three fields on the document fill it:

  fillers on the function        a phrase for the moment this tool is called
  wait_file on the function      audio looped while the tool is still running
  function_fillers per language  the phrase pool for any tool, in that language

The function-level `fillers` dict takes one language key: the bundled 3.0.1
schema defines it as one-of-one-language. Per-language coverage therefore
belongs on the `languages` entries, which the platform reads once
`languages_enabled` is on.

Written against signalwire-sdk 3.0.1.
"""
import os
import time

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# A hosted audio file the platform can fetch. This app does not serve one, so
# the wait file is only attached when you point at a real URL.
WAIT_FILE_URL = os.getenv("WAIT_FILE_URL", "").strip()

# Stand-in for a slow inventory system.
STOCK = {"SK-2210": 14, "SK-2211": 0, "SK-4400": 3}

# The phrase pools, in one place, so the languages below and the function
# share nothing by accident.
EN_FUNCTION_FILLERS = ["One moment while I check the shelf.",
                       "Let me look that up for you."]
ES_FUNCTION_FILLERS = ["Un momento, estoy comprobando.", "Deme un segundo."]
CHECK_STOCK_FILLER = ["Checking the warehouse now."]


def wait_file_fields():
    """`wait_file` and its loop count, only when there is a file to play."""
    if not WAIT_FILE_URL:
        return {}
    return {"wait_file": WAIT_FILE_URL, "wait_file_loops": 3}


class StockAgent(AgentBase):
    def __init__(self):
        super().__init__(name="stock", route="/stock")
        self.prompt_add_section(
            "Role",
            "You check parts inventory for a bicycle shop. Look the part up "
            "before you say anything about availability.",
        )
        # One pool of function fillers per language. Pass both kinds: with
        # only one, the SDK writes the deprecated single `fillers` key.
        self.add_language(
            "English", "en-US", "rime.spore",
            speech_fillers=["Right.", "Okay."],
            function_fillers=EN_FUNCTION_FILLERS,
        )
        self.add_language(
            "Spanish", "es-ES", "rime.spore",
            speech_fillers=["Vale.", "Claro."],
            function_fillers=ES_FUNCTION_FILLERS,
        )
        # Without this the platform ignores the languages list.
        self.set_params({"languages_enabled": True})

    @AgentBase.tool(
        name="check_stock",
        description=(
            "Look up how many of a part are in stock by its SKU. Use this "
            "before answering any question about availability."
        ),
        parameters={
            "type": "object",
            "properties": {
                "sku": {
                    "type": "string",
                    "description": ("The part's SKU: two letters, a dash, "
                                    "four digits, like SK-2210."),
                }
            },
            "required": ["sku"],
        },
        # One language key. This dict is one-of-one-language in the 3.0.1
        # schema; the per-language pools live on `languages` above.
        fillers={"en-US": CHECK_STOCK_FILLER},
        **wait_file_fields(),
    )
    def check_stock(self, args, raw_data):
        sku = (args.get("sku") or "").strip().upper()
        # The slow part. Set LOOKUP_DELAY_SECONDS on a real call to hear the
        # filler and the wait file; the platform covers this gap, not the model.
        time.sleep(float(os.getenv("LOOKUP_DELAY_SECONDS", "0")))
        if sku not in STOCK:
            return FunctionResult(
                f"NOT_FOUND: no part with SKU {sku}. Ask the caller to read "
                "the SKU again, letters then numbers."
            )
        count = STOCK[sku]
        if count == 0:
            return FunctionResult(f"Part {sku} is out of stock.")
        return FunctionResult(f"Part {sku}: {count} in stock.")


agent = StockAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
