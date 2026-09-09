"""Start from a prefab agent.

The SDK ships complete agents as classes. You pass configuration, not a prompt.
The prefab writes its prompt sections and registers its tools with their
handlers. The receptionist also sets its voice and wires its transfer.

  ReceptionistAgent  greets, records who is calling and why, transfers to a
                     department by name
  SurveyAgent        asks scripted questions in order, validates each answer
                     against its type, logs it

PREFAB selects which one this process serves. Both are built here so the
verifier can prove both.

Written against signalwire-sdk 3.0.1.
"""
import os

from dotenv import load_dotenv
from signalwire.prefabs import ReceptionistAgent, SurveyAgent

# the SDK does not read .env for you
load_dotenv()

# Every department the receptionist may transfer to. `name` becomes an enum on
# the transfer tool's argument, and the handler refuses a name that is not here.
DEPARTMENTS = [
    {"name": "sales", "description": "Pricing, availability and new orders",
     "number": os.getenv("SALES_NUMBER", "+15551230001")},
    {"name": "workshop", "description": "Repairs, servicing and appointments",
     "number": os.getenv("WORKSHOP_NUMBER", "+15551230002")},
]

# Each question carries a type; the prefab validates answers against it.
QUESTIONS = [
    {"id": "on_time", "type": "yes_no",
     "text": "Was your bike ready when we said it would be?"},
    {"id": "rating", "type": "rating", "scale": 5,
     "text": "From one to five, how would you rate the work?"},
    {"id": "notes", "type": "open_ended", "required": False,
     "text": "Anything else you want the workshop to know?"},
]


def build_receptionist():
    return ReceptionistAgent(
        departments=DEPARTMENTS,
        greeting="Ridgeline Cycles, how can I help?",
        name="reception", route="/reception",
    )


def build_survey():
    return SurveyAgent(
        survey_name="Workshop follow-up",
        brand_name="Ridgeline Cycles",
        questions=QUESTIONS,
        introduction="This is a short follow-up on your recent repair.",
        conclusion="Thanks. Your answers go straight to the workshop.",
        name="survey", route="/survey",
    )


BUILDERS = {"receptionist": build_receptionist, "survey": build_survey}

if __name__ == "__main__":
    which = os.getenv("PREFAB", "receptionist")
    BUILDERS[which]().serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
