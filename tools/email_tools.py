import imaplib
import smtplib
import email
from email.message import EmailMessage
from email.header import decode_header
import os
from dotenv import load_dotenv

load_dotenv()

EMAIL_ADDR = os.getenv('EMAIL_ADDRESS')
EMAIL_PASS = os.getenv('EMAIL_APP_PASSWORD')
IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')

def _decode_str(s):
    if not s: return ""
    decoded_list = decode_header(s)
    result = ""
    for decoded_string, charset in decoded_list:
        if isinstance(decoded_string, bytes):
            try:
                result += decoded_string.decode(charset or 'utf-8')
            except:
                result += decoded_string.decode('utf-8', errors='replace')
        else:
            result += str(decoded_string)
    return result

def check_inbox(limit: int = 3) -> str:
    """Connects to the email inbox via IMAP and returns the most recent UNREAD emails.
    Use this to monitor the user's inbox."""
    if not EMAIL_ADDR or EMAIL_PASS == 'your_app_password':
        return "Error: Email credentials not configured in .env"
        
    try:
        # Load previously processed email IDs
        processed_file = "processed_emails.json"
        try:
            import json
            with open(processed_file, "r") as f:
                processed_ids = set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            processed_ids = set()

        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL_ADDR, EMAIL_PASS)
        mail.select("inbox")
        
        status, messages = mail.search(None, 'UNSEEN')
        if status != "OK":
            return "No unread emails found."
            
        email_ids = messages[0].split()
        if not email_ids:
            return "Inbox zero! No unread emails."
            
        new_ids = [e_id for e_id in email_ids if e_id.decode('utf-8') not in processed_ids]
        if not new_ids:
            return "No new unread emails since last check."

        recent_ids = new_ids[-limit:]
        
        results = []
        for e_id in recent_ids:
            # Use PEEK so the email stays marked as UNREAD in the user's actual inbox
            status, msg_data = mail.fetch(e_id, '(BODY.PEEK[])')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject = _decode_str(msg.get("Subject"))
                    sender = _decode_str(msg.get("From"))
                    
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode()
                                except:
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode()
                        except:
                            pass
                            
                    results.append(f"From: {sender}\nSubject: {subject}\nBody: {body.strip()[:500]}...")
            
            # Mark as processed locally
            processed_ids.add(e_id.decode('utf-8'))
        
        mail.logout()

        # Save processed IDs so we don't spam the user next loop
        with open(processed_file, "w") as f:
            json.dump(list(processed_ids), f)

        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Error checking email: {e}"

def send_email(to_address: str, subject: str, body: str, from_address: str = None) -> str:
    """Sends an email using SMTP. Optionally specify 'from_address' to send from a linked alias. Use this to automatically reply to emails or notify someone."""
    if not EMAIL_ADDR or EMAIL_PASS == 'your_app_password':
        return "Error: Email credentials not configured in .env"
        
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = from_address if from_address else EMAIL_ADDR
        msg['To'] = to_address
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, 465)
        server.login(EMAIL_ADDR, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return f"Successfully sent email to {to_address} with subject '{subject}'"
    except Exception as e:
        return f"Error sending email: {e}"
