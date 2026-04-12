import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)

NOTIFY_EMAIL = "mondenel1996@gmail.com"


async def send_tender_email(new_tenders: list):
    if not new_tenders:
        return

    gmail_user = os.getenv("GMAIL_USER", "")
    gmail_pass = os.getenv("GMAIL_PASSWORD", "")

    if not gmail_pass:
        logger.warning("[EMAIL] GMAIL_PASSWORD not set — skipping")
        return

    rows = "".join([
        f"<tr style=border-bottom:1px solid #eee>"
        f"<td style=padding:10px 8px;font-size:14px;color:#111>{t.get(title,"")[:80]}</td>"
        f"<td style=padding:10px 8px;font-size:13px;color:#666>{t.get(issuing_body,"")}</td>"
        f"<td style=padding:10px 8px;font-size:13px;color:#666>{t.get(province,"")}</td>"
        f"<td style=padding:10px 8px;font-size:13px;color:#1D9E75>{t.get(industry_category,"")}</td>"
        f"</tr>"
        for t in new_tenders[:20]
    ])

    body = f"""
    <html><body style="font-family:sans-serif;max-width:700px;margin:0 auto;padding:20px">
      <div style="background:#1D9E75;padding:20px 24px;border-radius:12px 12px 0 0">
        <h1 style="color:white;margin:0;font-size:20px">TenderScout ZA</h1>
        <p style="color:#9FE1CB;margin:4px 0 0;font-size:14px">{len(new_tenders)} new tender(s) — {datetime.now().strftime("%d %b %Y %H:%M")}</p>
      </div>
      <div style="background:white;border:1px solid #eee;border-top:none;border-radius:0 0 12px 12px;padding:20px">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#f9f9f9">
              <th style="padding:8px;text-align:left;font-size:12px;color:#888">Title</th>
              <th style="padding:8px;text-align:left;font-size:12px;color:#888">Issuing Body</th>
              <th style="padding:8px;text-align:left;font-size:12px;color:#888">Province</th>
              <th style="padding:8px;text-align:left;font-size:12px;color:#888">Category</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="margin-top:20px;font-size:13px;color:#999">
          Log in at <a href="http://localhost:5173" style="color:#1D9E75">TenderScout ZA</a> to view full details.
        </p>
      </div>
    </body></html>
    """

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"TenderScout ZA — {len(new_tenders)} new tender(s) found"
        msg["From"] = gmail_user
        msg["To"] = NOTIFY_EMAIL
        msg.attach(MIMEText(body, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_user, gmail_pass)
            smtp.sendmail(gmail_user, NOTIFY_EMAIL, msg.as_string())
        logger.info(f"[EMAIL] Sent notification for {len(new_tenders)} tenders")
    except Exception as e:
        logger.error(f"[EMAIL] Failed: {e}")
