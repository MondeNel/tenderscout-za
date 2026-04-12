import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

load_dotenv()
logger = logging.getLogger(__name__)

GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD", "")


def _send(to_email: str, subject: str, html: str):
    if not GMAIL_USER or not GMAIL_PASSWORD:
        logger.warning("[EMAIL] Gmail credentials not set — skipping")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"TenderScout ZA <{GMAIL_USER}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_USER, GMAIL_PASSWORD)
            server.sendmail(GMAIL_USER, to_email, msg.as_string())
        logger.info(f"[EMAIL] Sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] Failed to send to {to_email}: {e}")
        return False


def _tender_rows_html(tenders: list) -> str:
    rows = ""
    for t in tenders:
        url = t.document_url or t.source_url or "#"
        closing = f"<span style='color:#ef4444'>Closes {t.closing_date}</span>" if t.closing_date else ""
        province = f"{t.town + ', ' if t.town else ''}{t.province or ''}"
        rows += f"""
        <tr>
          <td style="padding:12px 8px;border-bottom:1px solid #f3f4f6;vertical-align:top">
            <div style="font-size:14px;font-weight:600;color:#111827;margin-bottom:4px">{t.title}</div>
            <div style="font-size:12px;color:#6b7280">{t.issuing_body or ''} {'· ' + province if province.strip() else ''}</div>
            {('<div style="font-size:12px;margin-top:4px">' + closing + '</div>') if closing else ''}
          </td>
          <td style="padding:12px 8px;border-bottom:1px solid #f3f4f6;vertical-align:middle;text-align:right;white-space:nowrap">
            <a href="{url}" style="background:#1D9E75;color:#fff;padding:6px 14px;border-radius:6px;font-size:12px;text-decoration:none;font-weight:600">
              View
            </a>
          </td>
        </tr>"""
    return rows


def _build_email(user_name: str, tenders: list, total: int) -> str:
    rows = _tender_rows_html(tenders)
    preview_count = len(tenders)
    more = f"<p style='color:#6b7280;font-size:13px;text-align:center'>+ {total - preview_count} more tenders available — log in to see all</p>" if total > preview_count else ""
    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:Inter,system-ui,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;padding:32px 0">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;border:1px solid #e5e7eb;overflow:hidden">

        <!-- Header -->
        <tr>
          <td style="background:#1D9E75;padding:24px 32px">
            <div style="display:flex;align-items:center;gap:12px">
              <span style="font-size:22px;font-weight:700;color:#fff">⚡ TenderScout ZA</span>
            </div>
            <div style="color:#a7f3d0;font-size:13px;margin-top:4px">Procurement intelligence</div>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px">
            <h2 style="margin:0 0 6px;font-size:18px;color:#111827">
              {total} new tender{'s' if total != 1 else ''} matching your profile
            </h2>
            <p style="margin:0 0 20px;color:#6b7280;font-size:14px">
              Hi {user_name.split()[0]}, here's your latest tender update from TenderScout ZA.
            </p>

            <!-- Tender table -->
            <table width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;overflow:hidden">
              <thead>
                <tr style="background:#f9fafb">
                  <th style="padding:10px 8px;text-align:left;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Tender</th>
                  <th style="padding:10px 8px;text-align:right;font-size:11px;color:#9ca3af;font-weight:600;text-transform:uppercase;letter-spacing:.05em">Link</th>
                </tr>
              </thead>
              <tbody>{rows}</tbody>
            </table>

            {more}

            <!-- CTA -->
            <div style="text-align:center;margin-top:24px">
              <a href="http://localhost:5173/dashboard"
                style="background:#1D9E75;color:#fff;padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;display:inline-block">
                View all tenders →
              </a>
            </div>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:16px 32px;border-top:1px solid #f3f4f6;background:#f9fafb">
            <p style="margin:0;font-size:11px;color:#9ca3af;text-align:center">
              You're receiving this because you have tender alerts enabled on TenderScout ZA.<br>
              Preferences can be updated in your <a href="http://localhost:5173/account" style="color:#1D9E75">Account settings</a>.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_admin_notification(new_count: int):
    """Notify admin that new tenders were scraped."""
    if not GMAIL_USER:
        return
    html = f"<p>{new_count} new tenders were scraped and added to the TenderScout ZA database.</p>"
    _send(GMAIL_USER, f"[TenderScout ZA] {new_count} new tenders scraped", html)


def send_user_alerts(db):
    """
    Sends each user a digest of new tenders matching their preferences,
    scraped in the last cycle. Only fires if matching tenders exist.
    """
    from models import User, Tender
    from sqlalchemy import or_
    from datetime import datetime, timedelta

    # Only look at tenders scraped in the last 70 seconds (slightly > scheduler interval)
    cutoff = datetime.utcnow() - timedelta(seconds=70)

    try:
        users = db.query(User).filter(User.is_active == True).all()
        for user in users:
            if not user.email:
                continue

            ind_prefs = user.industry_preferences or []
            prov_prefs = user.province_preferences or []

            # Build filter — match any preferred industry OR province
            filters = []
            if ind_prefs:
                filters.append(Tender.industry_category.in_(ind_prefs))
            if prov_prefs:
                filters.append(Tender.province.in_(prov_prefs))

            if not filters:
                continue  # user has no preferences set yet

            matching = (
                db.query(Tender)
                .filter(
                    Tender.scraped_at >= cutoff,
                    or_(*filters),
                    Tender.is_active == True,
                )
                .order_by(Tender.scraped_at.desc())
                .all()
            )

            if not matching:
                continue

            total = len(matching)
            preview = matching[:10]  # cap email at 10 tenders

            html = _build_email(user.full_name, preview, total)
            subject = f"[TenderScout ZA] {total} new tender{'s' if total != 1 else ''} for you"
            _send(user.email, subject, html)

    except Exception as e:
        logger.error(f"[EMAIL] send_user_alerts failed: {e}")
