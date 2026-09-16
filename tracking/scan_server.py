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
copy of the real scan AND location data periodically rather than relying
solely on the live server's disk. /admin is a mobile-friendly page for
adding placement locations while out in the field -- bookmark it on your
phone rather than needing a laptop to run tracking/locations.py's
add_location(). Both are protected by the same SCAN_EXPORT_TOKEN so a
random visitor can't read or write your data -- set that environment
variable before deploying, and pass ?token=<value> to use either route.
"""

import os
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from locations import add_location, load_locations  # noqa: E402
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
    """Lets a hosting platform (or you) confirm the server is up, without naming the project to any visitor."""
    return jsonify({"status": "ok"})


@app.route("/rsvp")
def rsvp_page():
    """The default scan destination -- see module docstring."""
    return RSVP_PAGE


@app.route("/s/<design_id>/<location_code>")
def track_scan(design_id, location_code):
    record_scan(design_id, location_code)
    landing_url = os.environ.get("LANDING_URL", "/rsvp")
    return redirect(landing_url, code=302)


def _require_token():
    """Shared guard for the operator-only routes below. Reuses SCAN_EXPORT_TOKEN
    rather than asking for yet another environment variable to configure."""
    expected = os.environ.get("SCAN_EXPORT_TOKEN")
    if not expected or request.values.get("token") != expected:
        abort(403)


@app.route("/export")
def export_scans():
    """Backup route: pull real scan AND location data in one shot. Free-tier
    hosting can have ephemeral disk storage that resets on redeploy, so this
    is meant to be hit periodically during a campaign, not just once."""
    _require_token()
    return jsonify({"scans": load_scans(), "locations": load_locations()})


ADMIN_PAGE_TEMPLATE = """
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Add location</title>
<style>
  body {{ background: #111; color: #eee; font-family: -apple-system, "Segoe UI", sans-serif;
          margin: 0; padding: 20px; font-size: 16px; }}
  h1 {{ font-size: 1.2rem; }}
  label {{ display: block; margin-top: 14px; font-size: 0.9rem; color: #aaa; }}
  input {{ width: 100%; box-sizing: border-box; padding: 12px; font-size: 16px;
           border-radius: 6px; border: 1px solid #444; background: #1c1c1c; color: #eee; margin-top: 4px; }}
  button {{ margin-top: 18px; width: 100%; padding: 14px; font-size: 16px; font-weight: bold;
            border-radius: 6px; border: none; background: #39FF88; color: #000; }}
  .msg {{ margin-top: 14px; padding: 10px; border-radius: 6px; background: #163; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; font-size: 0.85rem; }}
  td, th {{ text-align: left; padding: 6px 4px; border-bottom: 1px solid #333; }}
</style>
</head>
<body>
  <h1>Add a placement location</h1>
  {message}
  <form method="POST" action="/admin?token={token}">
    <label>Location code (short, unique, e.g. annex_01)</label>
    <input name="location_code" required>
    <label>Description (cross street, landmark)</label>
    <input name="description" required>
    <label>Neighbourhood</label>
    <input name="neighbourhood" required>
    <button type="submit">Save location</button>
  </form>
  <table>
    <tr><th>Code</th><th>Description</th><th>Neighbourhood</th></tr>
    {rows}
  </table>
</body>
</html>
"""


@app.route("/admin", methods=["GET", "POST"])
def admin_locations():
    """
    Mobile-friendly page for adding placement locations while physically out
    putting posters up -- bookmark https://<your-domain>/admin?token=<token>
    on your phone. Replaces having to run Python locally to call
    tracking/locations.py's add_location().
    """
    _require_token()
    token = request.values.get("token")
    message = ""

    if request.method == "POST":
        try:
            add_location(
                location_code=request.form["location_code"].strip(),
                description=request.form["description"].strip(),
                neighbourhood=request.form["neighbourhood"].strip(),
            )
            message = '<div class="msg">Saved.</div>'
        except ValueError as exc:
            message = f'<div class="msg">Error: {escape(str(exc))}</div>'

    rows = "".join(
        f"<tr><td>{escape(loc['location_code'])}</td>"
        f"<td>{escape(loc['description'])}</td>"
        f"<td>{escape(loc['neighbourhood'])}</td></tr>"
        for loc in reversed(load_locations())
    )
    return ADMIN_PAGE_TEMPLATE.format(message=message, token=escape(token or ""), rows=rows)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
