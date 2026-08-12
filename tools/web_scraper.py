import urllib.request
import re
from html import unescape


def fetch_webpage_content(url: str, max_chars: int = 4000) -> str:
    """Fetches the content of a web page URL and extracts readable text.
    Use this tool when you need to read full article content, documentation, or webpage details."""
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"Cannot scrape non-text content type: {content_type}"

            html_bytes = response.read()
            html = html_bytes.decode("utf-8", errors="ignore")

        # Extract title
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = unescape(title_match.group(1)).strip() if title_match else "No title"

        # Remove script, style, header, footer, nav tags
        html_cleaned = re.sub(
            r"<(script|style|header|footer|nav|noscript|svg)[^>]*>.*?</\1>",
            "",
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # Remove HTML comments
        html_cleaned = re.sub(r"<!--.*?-->", "", html_cleaned, flags=re.DOTALL)

        # Replace structural block tags with newlines
        html_cleaned = re.sub(r"<(p|h[1-6]|div|li|br|tr)[^>]*>", "\n", html_cleaned, flags=re.IGNORECASE)

        # Strip remaining HTML tags
        text = re.sub(r"<[^>]+>", "", html_cleaned)
        text = unescape(text)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        cleaned_text = "\n".join(lines)

        if len(cleaned_text) > max_chars:
            cleaned_text = cleaned_text[:max_chars] + f"\n\n[...Truncated after {max_chars} characters...]"

        return f"Title: {title}\nURL: {url}\n\nContent:\n{cleaned_text}"

    except Exception as e:
        return f"Error fetching webpage '{url}': {e}"


def web_scraper(url: str, max_chars: int = 4000) -> str:
    """Scrapes and extracts full text content from a web page URL.
    Use this tool to read full webpage articles, documentation, or site text."""
    return fetch_webpage_content(url, max_chars=max_chars)
