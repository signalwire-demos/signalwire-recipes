"""Embed a call widget with no backend.

The Click-to-Call widget guide
(https://signalwire.com/docs/browser-sdk/guides/click-to-call-widget) puts a
call button on a page with one script tag and one element:
`<sw-click-to-call token="c2c_..." destination="/public/support">`. The token
is "created from a Click to Call resource in the dashboard", and the widget
"routes through embeds.signalwire.com automatically", so no server of yours is
in the call path. This Flask app only serves the page. It reads no API
credentials, and the call never touches it.

Written against Flask. There is no SDK call here.
"""
import html
import os

from dotenv import load_dotenv
from flask import Flask, Response

# the SDK does not read .env for you
load_dotenv()

C2C_TOKEN = os.getenv("CLICK_TO_CALL_TOKEN")
DESTINATION = os.getenv("DESTINATION", "/public/support")
LABEL = os.getenv("LABEL", "Talk to the workshop")
if not C2C_TOKEN:
    raise SystemExit("CLICK_TO_CALL_TOKEN is required: Dashboard, Tools, Click to Call")

WIDGET_SCRIPT = ("https://unpkg.com/@signalwire/web-components/dist/embed/"
                 "signalwire-web-components-embed.iife.js")

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ridgeline Cycles</title>
  <script src="{script}"></script>
</head>
<body>
  <h1>Ridgeline Cycles</h1>
  <p>Questions about a repair? Talk to us from this page.</p>
  <sw-click-to-call token="{token}" destination="{destination}"
                    label="{label}"></sw-click-to-call>
</body>
</html>
"""


def page(token=None, destination=None, label=None):
    """The page. Every attribute value is HTML-escaped on the way in."""
    return PAGE.format(script=WIDGET_SCRIPT,
                       token=html.escape(token or C2C_TOKEN, quote=True),
                       destination=html.escape(destination or DESTINATION, quote=True),
                       label=html.escape(label or LABEL, quote=True))


app = Flask(__name__)


@app.get("/")
def index():
    return Response(page(), mimetype="text/html")


if __name__ == "__main__":
    app.run(port=int(os.getenv("PORT", "8080")))
