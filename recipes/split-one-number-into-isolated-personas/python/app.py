"""Split one number into isolated personas.

One agent, three personas. The `default` context finds out why the caller
rang and can move to `sales`, `support` or `billing`. Each persona is its own
context with `isolated` set, so entering it wipes the conversation history
down to that context's prompt. Each persona's step names only its own tool in
`functions`, so the platform offers the model the sales tool only while sales
is on the line. The structure, not the prompt, keeps them apart. The tools are stubs
with fixed replies.

Written against signalwire-sdk 3.0.1 (contexts and steps).
"""
import os

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

PERSONAS = {
    "sales": ("You are the sales desk for Ridgeline Cycles. Quote prices for bikes "
              "and accessories.", ["quote_price"]),
    "support": ("You are the workshop support desk for Ridgeline Cycles. Book "
                "repair appointments.", ["book_repair"]),
    "billing": ("You are the billing desk for Ridgeline Cycles. Look up invoices.",
                ["look_up_invoice"]),
}


class FrontDoorAgent(AgentBase):
    def __init__(self):
        super().__init__(name="front-door", route="/front-door")
        self.prompt_add_section(
            "Role", "You answer one number for a bicycle shop and route the caller.")

        contexts = self.define_contexts()
        triage = contexts.add_context("default")
        triage.add_step("ask") \
            .add_section("Current Task",
                         "Find out whether the caller needs sales, support or "
                         "billing, then move to that context.") \
            .set_step_criteria("The caller has said which desk they need.") \
            .set_functions([]) \
            .set_valid_contexts(list(PERSONAS))

        for name, (prompt, tools) in PERSONAS.items():
            ctx = contexts.add_context(name)
            # entering this context wipes the history to this prompt alone
            ctx.set_isolated(True)
            ctx.add_section("Role", prompt)
            ctx.add_step("help") \
                .add_section("Current Task", "Help the caller with this desk's work.") \
                .set_step_criteria("The caller's request is handled.") \
                .set_functions(tools) \
                .set_valid_contexts(["default"]) \
                .set_end(True)

    @AgentBase.tool(name="quote_price", description="Quote the price of an item.",
                    parameters={"type": "object", "properties": {
                        "item": {"type": "string"}}, "required": ["item"]})
    def quote_price(self, args, raw_data):
        return FunctionResult(f"{args.get('item')} is 89.00.")

    @AgentBase.tool(name="book_repair", description="Book a workshop appointment.",
                    parameters={"type": "object", "properties": {
                        "day": {"type": "string"}}, "required": ["day"]})
    def book_repair(self, args, raw_data):
        return FunctionResult(f"Booked for {args.get('day')}.")

    @AgentBase.tool(name="look_up_invoice", description="Look up an invoice by number.",
                    parameters={"type": "object", "properties": {
                        "number": {"type": "string"}}, "required": ["number"]})
    def look_up_invoice(self, args, raw_data):
        return FunctionResult(f"Invoice {args.get('number')}: 45.00, paid.")


agent = FrontDoorAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
