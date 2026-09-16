"""
Stage 7, Tier 3: human review notification.

Sends one email summarizing every poster the quality gate flagged (failed
a Tier 1 check, or Tier 2 raised concerns or wasn't configured), so a
human can approve or reject each before it goes to print.

Requires GMAIL_ADDRESS, GMAIL_APP_PASSWORD (a Gmail "app password", not
your normal login password -- generate one at
myaccount.google.com/apppasswords, requires 2-factor auth enabled on the
account), and NOTIFY_EMAIL (where the summary goes -- can be the same
address). If any are missing, send_flagged_notification() prints the
summary to the console and setup instructions instead of sending -- the
same graceful-degradation pattern as the other external integrations in
this project (OPENAI_API_KEY, ANTHROPIC_API_KEY).
"""

import os
import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def _format_summary(flagged: list[dict]) -> str:
    lines = [f"{len(flagged)} poster(s) flagged for review:\n"]
    for item in flagged:
        lines.append(f"- {item['design_id']} / {item['location_code']} ({item['poster_image_path']})")
        lines.append(f"  status: {item['status']}")
        for check_name, check in item.get("tier1", {}).get("checks", {}).items():
            if not check["passed"]:
                lines.append(f"  tier1 FAILED [{check_name}]: {check['detail']}")
        tier2 = item.get("tier2") or {}
        if tier2.get("concerns"):
            lines.append(f"  tier2 concerns: {', '.join(tier2['concerns'])}")
        if tier2.get("configured") is False:
            lines.append("  tier2: not configured (ANTHROPIC_API_KEY not set)")
        lines.append("")
    return "\n".join(lines)


def send_flagged_notification(flagged: list[dict]) -> bool:
    """
    Email a summary of flagged posters for human review. Returns True if
    an email was actually sent, False if it just printed the summary
    (credentials not configured, or nothing to notify) -- flagged posters
    aren't lost either way, since run_quality_gate() also returns the
    full result list.
    """
    if not flagged:
        print("No posters flagged -- nothing to notify.")
        return False

    summary = _format_summary(flagged)

    sender = os.environ.get("GMAIL_ADDRESS")
    app_password = os.environ.get("GMAIL_APP_PASSWORD")
    recipient = os.environ.get("NOTIFY_EMAIL")

    if not (sender and app_password and recipient):
        print(
            "GMAIL_ADDRESS / GMAIL_APP_PASSWORD / NOTIFY_EMAIL not fully set -- "
            "printing the flagged summary instead of emailing it:\n"
        )
        print(summary)
        return False

    message = EmailMessage()
    message["Subject"] = f"Marketing engine: {len(flagged)} poster(s) need review"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(summary)

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(sender, app_password)
        server.send_message(message)

    return True
