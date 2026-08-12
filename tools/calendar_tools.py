import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()


def _get_google_access_token():
    """Attempts to exchange refresh token or service account for a Google API access token."""
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        try:
            url = "https://oauth2.googleapis.com/token"
            data = urllib.parse.urlencode({
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                return result.get("access_token")
        except Exception as e:
            print(f"[Nova Calendar] Google token exchange error: {e}")

    # Check Service Account JSON file path or inline JSON
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json and os.path.exists(sa_json):
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
            creds = service_account.Credentials.from_service_account_file(
                sa_json, scopes=['https://www.googleapis.com/auth/calendar']
            )
            creds.refresh(Request())
            return creds.token
        except Exception as e:
            print(f"[Nova Calendar] Service account auth error: {e}")

    return None


def _format_datetime(dt_str: str) -> str:
    """Helper to ensure ISO format datetime strings."""
    try:
        dt_str = dt_str.strip().replace(" ", "T")
        if "T" not in dt_str:
            dt_str += "T09:00:00"
        return dt_str
    except Exception:
        return dt_str


def create_calendar_event(title: str, start_time: str, end_time: str = None, description: str = "", location: str = "", attendees: str = "") -> str:
    """Schedules a meeting/event on Google Calendar.
    - title: Title of the meeting or event
    - start_time: Start datetime (e.g. '2026-08-15T14:00:00' or '2026-08-15 14:00')
    - end_time: End datetime (optional, defaults to 1 hour after start_time)
    - description: Optional details or agenda
    - location: Optional location or meeting link
    - attendees: Optional comma-separated email addresses of attendees"""
    
    start_iso = _format_datetime(start_time)
    if not end_time:
        try:
            dt_start = datetime.fromisoformat(start_iso)
            dt_end = dt_start + timedelta(hours=1)
            end_iso = dt_end.isoformat()
        except Exception:
            end_iso = start_iso
    else:
        end_iso = _format_datetime(end_time)

    calendar_id = os.getenv("GOOGLE_CALENDAR_ID") or os.getenv("EMAIL_ADDRESS") or "primary"
    token = _get_google_access_token()

    if token:
        try:
            url = f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events"
            event_body = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": start_iso, "timeZone": "UTC"},
                "end": {"dateTime": end_iso, "timeZone": "UTC"},
            }

            if attendees:
                attendee_list = [{"email": a.strip()} for a in attendees.split(",") if a.strip()]
                if attendee_list:
                    event_body["attendees"] = attendee_list

            data = json.dumps(event_body).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                html_link = result.get("htmlLink", "")
                return f"Successfully created Google Calendar event '{title}' for {start_iso}. Link: {html_link}"
        except Exception as e:
            print(f"[Nova Calendar] Google Calendar API request failed: {e}")

    # Fallback: Save local .ics calendar file
    try:
        os.makedirs("events", exist_ok=True)
        safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_")).rstrip().replace(" ", "_")
        filename = f"events/{safe_title}_{start_iso[:10]}.ics"

        ics_content = (
            "BEGIN:VCALENDAR\n"
            "VERSION:2.0\n"
            "PRODID:-//Nova AI Assistant//EN\n"
            "BEGIN:VEVENT\n"
            f"SUMMARY:{title}\n"
            f"DESCRIPTION:{description}\n"
            f"LOCATION:{location}\n"
            f"DTSTART:{start_iso.replace('-', '').replace(':', '')}\n"
            f"DTEND:{end_iso.replace('-', '').replace(':', '')}\n"
            "END:VEVENT\n"
            "END:VCALENDAR\n"
        )
        with open(filename, "w") as f:
            f.write(ics_content)

        return (
            f"Calendar event '{title}' scheduled for {start_iso}.\n"
            f"(Saved locally as {filename}. Configure GOOGLE_REFRESH_TOKEN or GOOGLE_SERVICE_ACCOUNT_JSON in Environment to sync directly to Google Calendar.)"
        )
    except Exception as e:
        return f"Error creating calendar event: {e}"


def list_calendar_events(limit: int = 5) -> str:
    """Lists upcoming scheduled calendar events."""
    calendar_id = os.getenv("GOOGLE_CALENDAR_ID") or os.getenv("EMAIL_ADDRESS") or "primary"
    token = _get_google_access_token()

    if token:
        try:
            now_iso = datetime.utcnow().isoformat() + "Z"
            url = f"https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(calendar_id)}/events?timeMin={urllib.parse.quote(now_iso)}&maxResults={limit}&singleEvents=true&orderBy=startTime"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                if not items:
                    return "No upcoming events found on Google Calendar."
                events = []
                for item in items:
                    start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
                    events.append(f"- {item.get('summary')} at {start}")
                return "Upcoming Google Calendar Events:\n" + "\n".join(events)
        except Exception as e:
            print(f"[Nova Calendar] Google Calendar list failed: {e}")

    # Fallback: List local .ics files
    if os.path.exists("events"):
        files = sorted(os.listdir("events"))
        if files:
            return "Local Scheduled Events (.ics files):\n" + "\n".join(f"- {f}" for f in files[:limit])

    return "No upcoming calendar events found."
