"""
Stage 4: scan tracking server.

A minimal Flask web server. When someone scans a poster's QR code, their
phone opens a URL built by Stage 2 (tracking/qr_generator.py), of the form:

    https://<your-domain>/s/<design_id>/<location_code>

This server receives that request, logs it (tracking/scans.py), and
redirects the visitor on to Prowler's landing page or app store listing.

PROWLER_LANDING_URL isn't set yet, because Prowler doesn't have a landing
page or app store listing to send people to (see CLAUDE.md's dependency
table). Until it is, this responds with a JSON confirmation instead of a
redirect -- so the server, the logging, and real QR codes can all be
tested end to end right now. The moment PROWLER_LANDING_URL is set, real
scans redirect to the real destination with no other code changes needed.

Run locally with:
    python tracking/scan_server.py
Then visit e.g. http://localhost:5000/s/gen1-20b2d3fc/loc001

Deploy for real by pushing this repo to a host like Railway, Render, or
Fly.io (see CLAUDE.md's Tools and Accounts Needed) and pointing
tracking/qr_generator.py's BASE_TRACKING_URL at that host's real domain --
QR codes already generated point at a placeholder domain and will need
regenerating once a real one exists, since a printed QR code's URL can't
be changed after the fact.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scans import record_scan  # noqa: E402

from flask import Flask, jsonify, redirect

app = Flask(__name__)


@app.route("/")
def health_check():
    """Lets a hosting platform (or you) confirm the server is up."""
    return jsonify({"status": "ok", "service": "genuance-marketing-engine scan tracker"})


@app.route("/s/<design_id>/<location_code>")
def track_scan(design_id, location_code):
    record_scan(design_id, location_code)

    landing_url = os.environ.get("PROWLER_LANDING_URL")
    if landing_url:
        return redirect(landing_url, code=302)

    return jsonify(
        {
            "status": "scan logged",
            "design_id": design_id,
            "location_code": location_code,
            "note": (
                "PROWLER_LANDING_URL is not set, so this scan was logged but not "
                "redirected anywhere. Once Prowler has a landing page or app store "
                "listing, set that environment variable and real scans will redirect "
                "there instead of returning this message."
            ),
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
