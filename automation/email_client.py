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
                        raw_subject = msg.get("subject", "No Subject")
                        raw_sender = msg.get("from", "Unknown Sender")

                        clean_subject = self._decode_header_str(raw_subject)
                        clean_sender = self._decode_header_str(raw_sender)

                        # Clean sender format e.g. "Google Cloud <no-reply@google.com>" -> "Google Cloud"
                        if "<" in clean_sender:
                            clean_sender = clean_sender.split("<")[0].strip().strip('"').strip("'")
                        if not clean_sender:
                            clean_sender = "Unknown Sender"

                        emails_list.append({"sender": clean_sender, "subject": clean_subject, "from": clean_sender})
            mail.logout()
        except Exception as e:
            logger.error(f"Failed to fetch unread emails: {e}")
            if "Application-specific password required" in str(e) or "AUTHENTICATIONFAILED" in str(e):
                return [{"from": "Google Security", "subject": "App Password Required", "date": "", "body": "Google 2FA is active. Please generate a 16-character App Password at myaccount.google.com/apppasswords."}]

        return emails_list

    def _decode_header_str(self, header_val: str) -> str:
        """Decodes MIME encoded header strings into readable UTF-8 text and sanitizes emojis."""
        if not header_val:
            return ""
        try:
            import re
            from email.header import decode_header
            decoded_parts = decode_header(header_val)
            result = []
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    result.append(part.decode(encoding or "utf-8", errors="ignore"))
                else:
                    result.append(str(part))
            text = "".join(result).strip()
            # Strip non-ASCII emojis / symbols that cause TTS or console encoding issues
            clean_text = text.encode("ascii", "ignore").decode("ascii").strip()
            return clean_text if clean_text else text
        except Exception:
            return str(header_val)
