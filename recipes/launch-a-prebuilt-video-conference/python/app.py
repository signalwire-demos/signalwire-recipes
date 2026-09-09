"""Launch a prebuilt video conference.

One POST creates a themed video conference. A second GET lists the tokens the
spec documents for it, each with a `name`, a `token` and its `scopes`. You
pass a `display_name`. `launch` always sends a layout, a quality and the
primary theme colour, which you may override. It adds a join window and a
`name` only when you give them. You get back an `id`, which is what the
token listing takes. The reference calls these conferences prebuilt, with no
code required, so nothing here is a Browser SDK client of your own.

Written against signalwire-sdk 3.0.1 (RestClient.video.conferences).
"""
from dotenv import load_dotenv
from signalwire.rest import RestClient

# the SDK does not read .env for you
load_dotenv()

# RestClient() reads SIGNALWIRE_PROJECT_ID / SIGNALWIRE_API_TOKEN /
# SIGNALWIRE_SPACE from the environment (signalwire/rest/client.py).
client = RestClient()


def launch(display_name, *, name=None, record_on_start=False, quality="720p",
           layout="grid-responsive", primary="#F72A72", join_from=None, join_until=None):
    """Create the conference. `display_name` is the spec's one required field;
    the rest are its documented options."""
    body = {"display_name": display_name, "record_on_start": record_on_start,
            "quality": quality, "layout": layout,
            "light_primary": primary, "dark_primary": primary}
    optional = (("name", name), ("join_from", join_from), ("join_until", join_until))
    for key, value in optional:
        if value:
            body[key] = value
    return client.video.conferences.create(**body)


def tokens(conference_id):
    """The tokens the platform minted for the conference, by name and scopes."""
    return client.video.conferences.list_conference_tokens(conference_id)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        raise SystemExit("usage: python app.py '<display name>' [slug]")
    conf = launch(sys.argv[1], name=sys.argv[2] if len(sys.argv) > 2 else None)
    print(conf)
    print(tokens(conf["id"]))
