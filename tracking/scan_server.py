"""
Stage 4: scan tracking server.

A minimal Flask web server. When someone scans a poster's QR code, their
phone opens a URL built by Stage 2 (tracking/qr_generator.py), of the form:

    https://<your-domain>/s/<design_id>/<location_code>

This server receives that request, logs it (tracking/scans.py), and
redirects the visitor to a landing page.

Current campaign is a test, not a real product launch: the "event" being
advertised isn't real (it's a placeholder used purely to see which ad
designs get people to scan and where). So rather than depending on a real
product landing page, this server hosts its own destination at /rsvp --
a simple "you're on the list" confirmation page. LANDING_URL can override
that with any other destination later (e.g. once there IS a real product
to send people to); if unset, it defaults to this server's own /rsvp.

Run locally with:
    python tracking/scan_server.py
Then visit e.g. http://localhost:5000/s/gen1-20b2d3fc/loc001

Deploy for real by pushing this repo to a host like Render, Railway, or
Fly.io and pointing tracking/qr_generator.py's BASE_TRACKING_URL at that
host's real domain -- QR codes already generated point at a placeholder
domain and need regenerating once a real one exists, since a printed QR
code's URL can't be changed after the fact.

/export is a lightweight backup route: free-tier hosting can have
ephemeral disk storage that resets on redeploy, so this lets you pull a
copy of the real scan log periodically rather than relying solely on the
live server's disk. Protected by SCAN_EXPORT_TOKEN so a random visitor
can't just read your data -- set that environment variable before
deploying, and query ?token=<value> to use it.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scans import load_scans, record_scan  # noqa: E402

from flask import Flask, abort, jsonify, redirect, request

app = Flask(__name__)

RSVP_PAGE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>THE UNLISTED</title>
<style>
  body { background: #0a0a0a; color: #f5f5f5; font-family: -apple-system, "Segoe UI", sans-serif;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 24px; }
  .card { max-width: 420px; text-align: center; }
  h1 { font-size: 1.8rem; letter-spacing: 0.04em; margin-bottom: 0.5rem; }
  p { color: #b5b5b5; line-height: 1.5; }
</style>
</head>
<body>
  <div class="card">
    <h1>YOU'RE ON THE LIST</h1>
    <p>Details go out 24 hours before. Keep an eye on your inbox.</p>
  </div>
</body>
</html>
"""


@app.route("/")
def health_check():
    """Lets a hosting platform (or you) confirm the server is up."""
    return jsonify({"status": "ok", "service": "genuance-marketing-engine scan tracker"})


@app.route("/rsvp")
def rsvp_page():
    """The default scan destination -- see module docstring."""
    return RSVP_PAGE


@app.route("/s/<design_id>/<location_code>")
def track_scan(design_id, location_code):
    record_scan(design_id, location_code)
    landing_url = os.environ.get("LANDING_URL", "/rsvp")
    return redirect(landing_url, code=302)


@app.route("/export")
def export_scans():
    token = request.args.get("token")
    expected = os.environ.get("SCAN_EXPORT_TOKEN")
    if not expected or token != expected:
        abort(403)
    return jsonify(load_scans())


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
