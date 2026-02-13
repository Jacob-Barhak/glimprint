import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import logging
from typing import List, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SMTP_SERVER = os.environ.get("SMTP_SERVER", os.environ.get("EMAIL_SERVER", "localhost"))
SMTP_PORT = int(os.environ.get("SMTP_PORT", os.environ.get("EMAIL_PORT", 587)))
SMTP_USER = os.environ.get("SMTP_USER", os.environ.get("EMAIL_USERNAME"))
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", os.environ.get("EMAIL_PASSWORD"))

def send_email(from_email: str, to_email: str, subject: str, body: str, is_html: bool = False, cc_email: str = None):
    """
    Sends a single email.
    to_email: Comma-separated string of emails.
    cc_email: Comma-separated string of emails.
    """
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    if cc_email:
        msg['Cc'] = cc_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html' if is_html else 'plain'))

    # Connect to server
    if SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    else:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls() # Secure the connection
    
    if SMTP_USER and SMTP_PASSWORD:
        server.login(SMTP_USER, SMTP_PASSWORD)
        
    server.send_message(msg)
    server.quit()
    logger.info(f"Email sent to {to_email}")
    return True

def send_bulk_email(from_email: str, recipients: List[Dict[str, str]], subject_template: str, body_template: str):
    """
    Sends emails to a list of recipients.
    recipients: List of dicts, e.g. [{"email": "foo@bar.com", "name": "Foo"}]
    Templates can use {name}, {email} placeholders.
    """
    success_count = 0
    fail_count = 0
    
    # Establish connection once if possible, but for safety/simplicity let's do per-email or batch if robust.
    # Re-using connection IS better.
    
    # Establish connection once if possible
    # Re-using connection IS better.
    
    if SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    else:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        
    if SMTP_USER and SMTP_PASSWORD:
        server.login(SMTP_USER, SMTP_PASSWORD)

    for r in recipients:
        email = r.get("email")
        if not email: continue
        
        name = r.get("name", "")
        
        # Format content
        # Format content
        try:
            # Ensure basic keys exist to prevent KeyErrors if template uses them but dict doesn't have them
            format_context = r.copy()
            if "name" not in format_context: format_context["name"] = ""
            if "email" not in format_context: format_context["email"] = email
            if "affiliation" not in format_context: format_context["affiliation"] = ""
            
            sub = subject_template.format(**format_context)
            bod = body_template.format(**format_context)
        except Exception as e:
            logger.error(f"Template error for {email}: {e}")
            fail_count += 1
            continue

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = email
        msg['Subject'] = sub
        msg.attach(MIMEText(bod, 'html')) # Assume HTML for announcements

        try:
            server.send_message(msg)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed sending to {email}: {e}")
            fail_count += 1
            
    try:
        server.quit()
    except: pass
    
    return success_count, fail_count
