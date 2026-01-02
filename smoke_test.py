import os
import sys
import time
import json
import urllib.request
import urllib.error
import urllib.parse

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None


def send_slack_notification(webhook_url, message):
    """Send a simple Slack message; no-op when webhook is falsy."""
    if not webhook_url:
        return
    data = json.dumps({"text": message}).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() >= 400:
                print(f"Error sending Slack notification: HTTP {resp.getcode()}")
    except Exception as e:
        print(f"Error sending Slack notification: {e}")

def run_smoke_check(url, webhook_url=None):
    """Navigate to URL with Playwright, report status, and optionally notify Slack."""
    if sync_playwright is None:
        print("Playwright is not installed. Run:\n  python -m pip install -r requirements.txt\n  python -m playwright install")
        sys.exit(1)

    start = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                context = browser.new_context(user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"))
                page = context.new_page()
                response = page.goto(url, timeout=45000)
                try:
                    page.wait_for_load_state("load", timeout=30000)
                except Exception:
                    pass

                status = response.status if response else None
                elapsed = time.time() - start
                print(f"HTTP {status} returned for {url} (time: {elapsed:.2f}s)")

                if status is None or status >= 400:
                    # Print some lightweight diagnostic headers (no body)
                    try:
                        headers = response.headers if response else {}
                        print("--- Response headers ---")
                        for k, v in headers.items():
                            print(f"{k}: {v}")
                    except Exception:
                        pass

                    host = urllib.parse.urlparse(url).netloc.split(':')[0]
                    short = f"FAIL — {status if status is not None else 'ERR'} — {host}"
                    send_slack_notification(webhook_url, short)
                    sys.exit(1)

                msg = f"Page responded with {status} in {elapsed:.2f} seconds (Playwright)."
                print("✅ Smoke check passed.")
                print(f"⏲️ {msg}")
                # Compact Slack message: "OK — {status} — {host}"
                host = urllib.parse.urlparse(url).netloc.split(':')[0]
                short = f"OK — {status} — {host}"
                send_slack_notification(webhook_url, short)

            finally:
                try:
                    context.close()
                except Exception:
                    pass
                browser.close()

    except Exception as e:
        print(f"Playwright error while requesting {url}: {e}")
        host = urllib.parse.urlparse(url).netloc.split(':')[0]
        short = f"ERR — {host}"
        send_slack_notification(webhook_url, short)
        sys.exit(1)


if __name__ == "__main__":
    url = os.environ.get("URL")
    webhook = os.environ.get("SLACK_WEBHOOK_URL") or None
    if not url:
        print("Error: set the URL environment variable (URL)")
        sys.exit(1)
    run_smoke_check(url, webhook)
