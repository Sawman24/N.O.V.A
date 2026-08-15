import imaplib
import smtplib
import email
from email.message import EmailMessage
from email.header import decode_header
import os
import json
import uuid
from dotenv import load_dotenv

load_dotenv()


def _decode_str(s):
    if not s:
        return ""
    decoded_list = decode_header(s)
    result = ""
    for decoded_string, charset in decoded_list:
        if isinstance(decoded_string, bytes):
            try:
                result += decoded_string.decode(charset or 'utf-8')
            except (UnicodeDecodeError, LookupError):
                result += decoded_string.decode('utf-8', errors='replace')
        else:
            result += str(decoded_string)
    return result


def _get_email_config():
    return {
        "address": os.getenv('EMAIL_ADDRESS'),
        "password": os.getenv('EMAIL_APP_PASSWORD'),
        "imap": os.getenv('IMAP_SERVER', 'imap.gmail.com'),
        "smtp": os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    }


def evaluate_email_triage(sender: str, subject: str, body: str) -> str:
    """Evaluates an incoming email against email_rules.json to determine if Nova can auto-reply or requires human approval.
    Returns a JSON string with decision: 'auto_reply_allowed' or 'requires_human_approval' and reason."""
    rules_path = "email_rules.json"
    default_rules = {
        "auto_reply_enabled": True,
        "require_approval_keywords": [
            "payment", "invoice", "contract", "legal", "salary", "job offer",
            "price", "quote", "urgent", "bank", "wire transfer", "password", "credential", "security"
        ],
        "whitelist_senders": [],
        "blacklist_senders": []
    }

    try:
        if os.path.exists(rules_path):
            with open(rules_path, "r") as f:
                rules = json.load(f)
        else:
            rules = default_rules
    except Exception:
        rules = default_rules

    if not rules.get("auto_reply_enabled", True):
        return json.dumps({
            "action": "requires_human_approval",
            "reason": "Auto-reply is globally disabled in email_rules.json."
        })

    sender_lower = sender.lower()
    for blocked in rules.get("blacklist_senders", []):
        if blocked.lower() in sender_lower:
            return json.dumps({
                "action": "blocked",
                "reason": f"Sender {sender} is blacklisted."
            })

    # Whitelisted senders override keyword checks
    for trusted in rules.get("whitelist_senders", []):
        if trusted.lower() in sender_lower:
            return json.dumps({
                "action": "auto_reply_allowed",
                "reason": f"Sender {sender} is on the trusted whitelist."
            })

    # Check sensitive keywords in subject or body
    combined_text = f"{subject} {body}".lower()
    matched_keywords = []
    for kw in rules.get("require_approval_keywords", []):
        if kw.lower() in combined_text:
            matched_keywords.append(kw)

    if matched_keywords:
        return json.dumps({
            "action": "requires_human_approval",
            "reason": f"Email contains sensitive keywords requiring human approval: {', '.join(matched_keywords)}"
        })

    return json.dumps({
        "action": "auto_reply_allowed",
        "reason": "Email passed triage checks with no sensitive keywords matched."
    })


def check_inbox(limit: int = 3) -> str:
    """Connects to the email inbox via IMAP and returns the most recent UNREAD emails.
    Use this to monitor the user's inbox."""
    cfg = _get_email_config()
    if not cfg["address"] or cfg["password"] == 'your_app_password':
        return "Error: Email credentials not configured in .env"

    try:
        processed_file = "processed_emails.json"
        try:
            with open(processed_file, "r") as f:
                processed_ids = set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            processed_ids = set()

        mail = imaplib.IMAP4_SSL(cfg["imap"])
        mail.login(cfg["address"], cfg["password"])
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
                                except (UnicodeDecodeError, AttributeError):
                                    pass
                    else:
                        try:
                            body = msg.get_payload(decode=True).decode()
                        except (UnicodeDecodeError, AttributeError):
                            pass

                    triage_result = evaluate_email_triage(sender, subject, body)
                    results.append(
                        f"From: {sender}\nSubject: {subject}\nTriage Status: {triage_result}\nBody: {body.strip()[:500]}..."
                    )

            processed_ids.add(e_id.decode('utf-8'))

        mail.logout()

        with open(processed_file, "w") as f:
            json.dump(list(processed_ids), f)

        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Error checking email: {e}"


def send_email(to_address: str, subject: str, body: str, from_address: str = None) -> str:
    """Sends an email using SMTP. Optionally specify 'from_address' to send from a linked alias. Use this to automatically reply to emails or notify someone."""
    cfg = _get_email_config()
    if not cfg["address"] or cfg["password"] == 'your_app_password':
        return "Error: Email credentials not configured in .env"

    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg['Subject'] = subject
        msg['From'] = from_address if from_address else cfg["address"]
        msg['To'] = to_address

        server = smtplib.SMTP_SSL(cfg["smtp"], 465)
        server.login(cfg["address"], cfg["password"])
        server.send_message(msg)
        server.quit()
        return f"Successfully sent email to {to_address} with subject '{subject}'"
    except Exception as e:
        return f"Error sending email: {e}"


def draft_email_reply(to_address: str, subject: str, body: str, reason: str = "") -> str:
    """Saves a pending draft reply when an email requires human approval. Nova calls this instead of send_email when triage flags an email."""
    drafts_file = "email_drafts.json"
    try:
        if os.path.exists(drafts_file):
            with open(drafts_file, "r") as f:
                drafts = json.load(f)
        else:
            drafts = []
    except Exception:
        drafts = []

    draft_id = str(uuid.uuid4())[:8]
    draft = {
        "id": draft_id,
        "to": to_address,
        "subject": subject,
        "body": body,
        "reason": reason,
        "status": "pending_approval"
    }
    drafts.append(draft)

    with open(drafts_file, "w") as f:
        json.dump(drafts, f, indent=2)

    return f"Draft saved (ID: {draft_id}). Saved for recipient '{to_address}'. Human approval required before sending. Reason: {reason}"


def list_pending_email_drafts() -> str:
    """Lists all email drafts currently waiting for human approval."""
    drafts_file = "email_drafts.json"
    try:
        if not os.path.exists(drafts_file):
            return "No pending email drafts."
        with open(drafts_file, "r") as f:
            drafts = json.load(f)
        pending = [d for d in drafts if d.get("status") == "pending_approval"]
        if not pending:
            return "No pending email drafts waiting for approval."
        return json.dumps(pending, indent=2)
    except Exception as e:
        return f"Error reading email drafts: {e}"


def approve_email_draft(draft_id: str) -> str:
    """Approves and sends a pending email draft by its draft_id."""
    drafts_file = "email_drafts.json"
    try:
        if not os.path.exists(drafts_file):
            return "No email drafts found."
        with open(drafts_file, "r") as f:
            drafts = json.load(f)

        target_draft = None
        for d in drafts:
            if d.get("id") == draft_id and d.get("status") == "pending_approval":
                target_draft = d
                break

        if not target_draft:
            return f"Pending draft with ID '{draft_id}' not found."

        res = send_email(target_draft["to"], target_draft["subject"], target_draft["body"])
        if "Successfully" in res:
            target_draft["status"] = "sent"
            with open(drafts_file, "w") as f:
                json.dump(drafts, f, indent=2)
            return f"Draft {draft_id} approved and sent to {target_draft['to']}!"
        else:
            return f"Failed to send draft {draft_id}: {res}"
    except Exception as e:
        return f"Error approving draft: {e}"
