"""Prove the claim without a network.

Claim: a `<sw-click-to-call>` element with a Click to Call token from the
Dashboard and a destination address puts a call button on a page, and no
server of yours is in the call path.

Proof: the Flask app serves one HTML page. The page loads the widget script
the guide names and holds exactly one `sw-click-to-call` element whose `token`,
`destination` and `label` attributes are the configured values, escaped. The
page carries no API token and no route other than the page. These are local
checks on the page; the routing through embeds.signalwire.com is the widget
guide's documented behaviour. Expected values live here, not in app.py.
"""
import os
import pathlib
import sys
from html.parser import HTMLParser

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "tools"))
sys.path.insert(0, str(HERE / "python"))
os.environ.update({
    "CLICK_TO_CALL_TOKEN": "c2c_verifier_only_0123456789abcdef",
    "DESTINATION": "/public/workshop",
    "LABEL": "Talk to the workshop",
})

import verifylib as V  # noqa: E402

SCRIPT = ("https://unpkg.com/@signalwire/web-components/dist/embed/"
          "signalwire-web-components-embed.iife.js")


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.widgets, self.scripts = [], []

    def handle_starttag(self, tag, attrs):
        if tag == "sw-click-to-call":
            self.widgets.append(dict(attrs))
        if tag == "script":
            self.scripts.append(dict(attrs).get("src"))


def main():
    V.sdk_banner()
    import app as recipe

    client = recipe.app.test_client()
    r = client.get("/")
    assert r.status_code == 200 and r.mimetype == "text/html", (r.status_code, r.mimetype)
    body = r.get_data(as_text=True)
    parsed = Elements()
    parsed.feed(body)
    assert parsed.scripts == [SCRIPT], parsed.scripts
    assert parsed.widgets == [{"token": "c2c_verifier_only_0123456789abcdef",
                               "destination": "/public/workshop",
                               "label": "Talk to the workshop"}], parsed.widgets
    # the page holds no credential-shaped value and the app has no other route;
    # local checks, not a proof about the call path
    assert "PT-" not in body and "proj-" not in body, body[:200]
    routes = sorted(str(rule) for rule in recipe.app.url_map.iter_rules() if rule.endpoint != "static")
    assert routes == ["/"], routes

    # attribute values are escaped, so a label with a quote cannot break out
    hostile = recipe.page(label='Talk" onclick="alert(1)')
    parsed = Elements()
    parsed.feed(hostile)
    assert parsed.widgets[0]["label"] == 'Talk" onclick="alert(1)', parsed.widgets
    assert "onclick" not in [k for w in parsed.widgets for k in w], parsed.widgets

    print(f"ok: the page loads the widget script and one sw-click-to-call with the configured token, "
          f"destination and label, escaped; it exposes one route and no API token")


if __name__ == "__main__":
    main()
