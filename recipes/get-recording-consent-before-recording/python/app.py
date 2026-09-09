"""Get recording consent before recording.

Recording starts from a tool result, never from the document. The consent tool
is the only thing in this agent that can emit a `record_call`, and it emits it
only when the caller actually agreed.

A step is a place in a flow, not a security boundary. `valid_steps` shapes the
navigation tool the model is offered, and step criteria is text the model
judges, so neither one keeps the caller out of the next step. The tool that
acts is therefore the thing that checks: `get_balance` refuses until the
recording question has actually been answered.

Written against signalwire-sdk 3.0.1.
"""
import os
import re

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

# Recording a call without disclosure is a legal problem in two-party consent
# jurisdictions, so the refusal path has to work as well as the happy path.
AGREED = {
    "yes", "yeah", "yep", "yes that is fine", "that is fine", "sure",
    "sure that is fine", "ok", "okay", "that is ok", "i agree", "go ahead",
    "yes go ahead", "fine", "no problem",
}
REFUSED = {
    "no", "nope", "no thanks", "no thank you", "do not", "no do not",
    "i would rather not", "rather not", "not ok", "no i do not",
    "i do not want that", "no i would rather not",
}

# Expanded before apostrophes are dropped, so "that's fine" and "that is fine"
# are the same answer.
CONTRACTIONS = {
    "that's": "that is", "thats": "that is", "it's": "it is",
    "i'd": "i would", "i'm": "i am", "don't": "do not", "dont": "do not",
    "doesn't": "does not", "can't": "can not", "cant": "can not",
    "won't": "will not", "isn't": "is not", "wouldn't": "would not",
}

# Politeness only. A hedge like "perhaps" or "maybe" changes the answer, so
# removing it would turn "perhaps, sure" into consent.
FILLER = ("um", "uh", "er", "well", "please")


def normalise(answer):
    """Reduce an utterance to a comparable form without changing its meaning."""
    said = (answer or "").strip().lower()
    said = re.sub(r"[^a-z' ]+", " ", said)
    words = []
    for word in said.split():
        word = CONTRACTIONS.get(word, word).replace("'", "")
        if word in FILLER:
            continue
        words.append(word)
    return " ".join(" ".join(words).split())


class IntakeAgent(AgentBase):
    def __init__(self):
        super().__init__(name="intake", route="/intake")
        self.prompt_add_section(
            "Role",
            "You take account queries for a credit union. Before anything "
            "else, tell the caller the call is recorded for quality and "
            "training, and ask whether that is alright.",
        )
        contexts = self.define_contexts()
        flow = contexts.add_context("default")

        disclose = flow.add_step("disclose")
        disclose.set_text(
            "Say that the call is recorded for quality and training, and ask "
            "whether the caller is alright with that. Pass exactly what they "
            "said to record_consent."
        )
        # a description the model judges; see the README on what this is worth
        disclose.set_step_criteria("The caller has answered the recording question.")
        disclose.set_functions(["record_consent"])
        # no native route onward: the handler decides
        disclose.set_valid_steps([])

        assist = flow.add_step("assist")
        assist.set_text("Help the caller with their account question.")
        assist.set_functions(["get_balance"])
        assist.set_valid_steps([])

    @AgentBase.tool(
        name="record_consent",
        description=(
            "Record whether the caller agreed to the call being recorded. "
            "Call this immediately after they answer, with their exact words."
        ),
        parameters={
            "type": "object",
            "properties": {
                "answer": {
                    "type": "string",
                    "description": "Exactly what the caller said, verbatim.",
                }
            },
            "required": ["answer"],
        },
    )
    def record_consent(self, args, raw_data):
        said = normalise(args.get("answer"))
        # Whole-answer matching, not substring. "yesterday" contains "yes" and
        # "I cannot say yes" contains it too; both would otherwise consent.
        if said in REFUSED:
            # Move on without recording. The call continues.
            return FunctionResult(
                "Understood, this call is not being recorded."
            ).update_global_data({"recording": "declined"}).swml_change_step("assist")
        if said not in AGREED:
            # Ambiguous is not consent.
            return FunctionResult(
                "UNCLEAR: that was not a yes or a no. Ask again, plainly, "
                "whether they are alright with the call being recorded."
            )
        # Only here does recording start, and it starts from this result.
        return (
            FunctionResult("Thank you. Starting the recording now.")
            .update_global_data({"recording": "consented"})
            .record_call(control_id="consented", stereo=True, direction="both")
            .swml_change_step("assist")
        )

    @AgentBase.tool(
        name="get_balance",
        description="Look up the caller's account balance.",
        parameters={"type": "object", "properties": {}},
    )
    def get_balance(self, args, raw_data):
        # Reaching this step is not permission to run. A step is a place in a
        # flow, not a security boundary, so the tool checks the state it
        # depends on rather than trusting how the call got here.
        answered = (raw_data or {}).get("global_data", {}).get("recording")
        if answered not in ("consented", "declined"):
            return FunctionResult(
                "NOT_DISCLOSED: the recording question has not been answered "
                "yet. Ask it and call record_consent before helping."
            )
        return FunctionResult("The balance is four hundred and twelve dollars.")


agent = IntakeAgent()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
