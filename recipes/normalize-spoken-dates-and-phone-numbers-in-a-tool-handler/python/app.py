"""Normalize spoken dates and phone numbers in a tool handler.

Speech recognition hands the model "next Tuesday" and "four one five, five
five five, oh one two three". The tool takes those words as they are; the
handler turns them into an ISO date and an E.164 number, writes the machine
values to `global_data`, and reads both back in words the caller can check.
When it cannot, it says so with a typed state and asks for the piece it needs.
The prompt never asks the model to convert anything.

Written against signalwire-sdk 3.0.1.
"""
import os
import re
from datetime import date, timedelta

from dotenv import load_dotenv
from signalwire import AgentBase, FunctionResult

# the SDK does not read .env for you
load_dotenv()

MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july",
               "august", "september", "october", "november", "december"]
MONTHS = {m: i for i, m in enumerate(MONTH_NAMES, 1)}
MONTHS.update({m[:3]: i for i, m in enumerate(MONTH_NAMES, 1)})
MONTHS["sept"] = 9
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
UNITS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
         "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
         "twelfth": 12, "thirteenth": 13, "fourteenth": 14, "fifteenth": 15,
         "sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19,
         "twentieth": 20, "thirtieth": 30}
TENS = {"twenty": 20, "thirty": 30}
DIGITS = {"zero": "0", "oh": "0", "o": "0", "one": "1", "two": "2", "three": "3",
          "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
               "nine"]
FILLER = {"on", "the", "of", "this", "at"}


def today():
    """The clock. TODAY pins it so the verifier's dates are stable."""
    pinned = os.getenv("TODAY")
    return date.fromisoformat(pinned) if pinned else date.today()


def _words(text):
    return re.sub(r"[^a-z0-9/]+", " ", (text or "").lower().replace("-", " ")).split()


def _next_weekday(start, name):
    """The next such weekday strictly after start."""
    delta = (WEEKDAYS.index(name) - start.weekday()) % 7 or 7
    return start + timedelta(days=delta)


def _resolve(month, day, year, start):
    """A calendar date, or None when the day does not exist in that month."""
    try:
        if year:
            return date(year, month, day)
        this_year = date(start.year, month, day)
        return this_year if this_year >= start else date(start.year + 1, month, day)
    except ValueError:
        return None


def normalize_date(text, start):
    """'tomorrow', 'next Tuesday', 'the fifth of March', 'March 5th', '9/30'.

    A weekday means the next one after today; 'next' adds a week. A month and
    day with no year mean the next time that date comes round.
    """
    words = _words(text)
    joined = " ".join(words)
    if joined == "today":
        return start
    if joined == "tomorrow":
        return start + timedelta(days=1)
    if joined in ("day after tomorrow", "the day after tomorrow"):
        return start + timedelta(days=2)
    core = [w for w in words if w not in FILLER]
    if len(core) == 1 and core[0] in WEEKDAYS:
        return _next_weekday(start, core[0])
    if len(core) == 2 and core[0] == "next" and core[1] in WEEKDAYS:
        return _next_weekday(start, core[1]) + timedelta(days=7)
    if len(core) == 1:
        m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", core[0])
        if m:
            return _resolve(int(m[1]), int(m[2]), int(m[3]) if m[3] else None, start)
    month = day = year = None
    i = 0
    while i < len(core):
        w = core[i]
        if w in MONTHS and month is None:
            month = MONTHS[w]
        elif w in TENS and i + 1 < len(core) and UNITS.get(core[i + 1], 10) < 10:
            day = TENS[w] + UNITS[core[i + 1]]
            i += 1
        elif w in UNITS:
            day = UNITS[w]
        elif re.fullmatch(r"\d{1,2}(st|nd|rd|th)?", w):
            day = int(re.sub(r"\D", "", w))
        elif re.fullmatch(r"\d{4}", w):
            year = int(w)
        else:
            return None
        i += 1
    if month is None or day is None:
        return None
    return _resolve(month, day, year, start)


def normalize_phone(text):
    """Spoken or written digits to E.164, North America assumed. None otherwise."""
    digits = "".join(DIGITS.get(w, w) for w in _words(text) if w in DIGITS or w.isdigit())
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def ordinal(n):
    if 11 <= n % 100 <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def spoken_date(d):
    """'Tuesday, September 8th': the weekday lets the caller catch a wrong date."""
    weekday = WEEKDAYS[d.weekday()].capitalize()
    month = MONTH_NAMES[d.month - 1].capitalize()
    return f"{weekday}, {month} {ordinal(d.day)}"


def spoken_phone(e164):
    """'four one five, five five five, zero one two three', grouped for reading back."""
    n = e164[2:]
    groups = (n[:3], n[3:6], n[6:])
    return ", ".join(" ".join(DIGIT_WORDS[int(c)] for c in g) for g in groups)


class CallbackDesk(AgentBase):
    def __init__(self):
        super().__init__(name="callback-desk", route="/callback")
        self.prompt_add_section(
            "Role",
            "You schedule callbacks for a repair shop. Pass the day and the number "
            "exactly as the caller says them; the tool converts them. Read back what "
            "the tool returns and ask the caller to confirm.",
        )

    @AgentBase.tool(
        name="schedule_callback",
        description=("Schedule a callback on a day at a phone number. Pass both as the "
                     "caller said them. Do not convert or reformat either one."),
        parameters={
            "type": "object",
            "properties": {
                "date": {"type": "string",
                         "description": ("The day in the caller's words: 'tomorrow', "
                                         "'next Tuesday', 'the fifth of March', "
                                         "'March 5th', '9/30'.")},
                "phone": {"type": "string",
                          "description": ("The number as spoken or read: 'four one five, "
                                          "five five five, oh one two three' or "
                                          "'(415) 555-0123'.")},
            },
            "required": ["date", "phone"],
        },
    )
    def schedule_callback(self, args, raw_data):
        date_text, phone_text = args.get("date"), args.get("phone")
        when = normalize_date(date_text, today())
        if when is None:
            return FunctionResult(
                f"UNPARSED_DATE: could not read {date_text!r} as a date. Ask the caller "
                "for the day and the month, then call again.")
        number = normalize_phone(phone_text)
        if number is None:
            return FunctionResult(
                f"UNPARSED_PHONE: {phone_text!r} was not a ten digit number. "
                "Ask the caller to say it digit by digit, then call again.")
        # the machine values go to global_data; the caller hears words
        result = FunctionResult(f"Callback set for {spoken_date(when)} at "
                                f"{spoken_phone(number)}. Read both back and ask the "
                                "caller to confirm.")
        result.update_global_data({"callback": {"date": when.isoformat(),
                                                "phone": number}})
        return result


agent = CallbackDesk()

if __name__ == "__main__":
    agent.serve(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
