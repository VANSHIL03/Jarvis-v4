"""
JARVIS v4 - Email Transport (IMAP/SMTP)
"""

import imaplib
import smtplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from utils.logger import logger

class EmailClient:
    def __init__(self, smtp_server: str = "smtp.gmail.com", imap_server: str = "imap.gmail.com"):
        self.smtp_server = smtp_server
        self.imap_server = imap_server
        self.port_smtp = 587
        self.port_imap = 993

    def send_email(self, sender_email: str, sender_password: str, recipient_email: str, subject: str, body: str) -> bool:
        """Sends an email using SMTP."""
        logger.info(f"Sending email to '{recipient_email}' with subject '{subject}'")
        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            server = smtplib.SMTP(self.smtp_server, self.port_smtp)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, recipient_email, msg.as_string())
            server.quit()
            logger.info("Email sent successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def fetch_unread_emails(self, user_email: str = "", user_password: str = "", limit: int = 5) -> List[Dict[str, str]]:
        """Fetches unread emails from IMAP inbox."""
        import os
        from config.settings import settings
        user_email = user_email or os.getenv("EMAIL_ADDRESS", getattr(settings, "EMAIL_ADDRESS", ""))
        user_password = user_password or os.getenv("EMAIL_PASSWORD", getattr(settings, "EMAIL_PASSWORD", ""))

        if not user_email or not user_password:
            logger.warning("Email credentials missing for IMAP fetch.")
            return [{"from": "System Alert", "subject": "Email Credentials Missing", "date": "", "body": "Please add EMAIL_ADDRESS and EMAIL_PASSWORD to .env or set up n8n gmail-read workflow."}]

        emails_list = []
        try:
            mail = imaplib.IMAP4_SSL(self.imap_server, self.port_imap)
            mail.login(user_email, user_password)
            mail.select("inbox")

            status, messages = mail.search(None, 'UNSEEN')
            email_ids = messages[0].split()

            for e_id in email_ids[-limit:]:
                _, msg_data = mail.fetch(e_id, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = msg.get("subject", "No Subject")
                        sender = msg.get("from", "Unknown Sender")
                        emails_list.append({"sender": sender, "subject": subject})
            mail.logout()
        except Exception as e:
            logger.error(f"Failed to fetch unread emails: {e}")

        return emails_list
