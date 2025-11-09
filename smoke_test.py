import os
import sys
import time
import json
import urllib.request
import urllib.error

try:
    from playwright.sync_api import sync_playwright
except Exception:
    sync_playwright = None

def send_slack_notification(webhook_url, message):
    if not webhook_url:
        print("Slack webhook not configured; skipping Slack notification.")
        return
    payload = {"text": message}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.getcode() >= 400:
                print(f"Error sending Slack notification: HTTP {resp.getcode()}")
    except urllib.error.URLError as e:
        print(f"Error sending Slack notification: {e}")

def check_console_errors(url, webhook_url):
    # Use Playwright-only to perform the smoke check (execute JS, bypass Cloudflare challenges)
    if sync_playwright is None:
        print("Playwright is not available. Please install dependencies and the browser binaries:\n  python -m pip install -r requirements.txt\n  python -m playwright install")
        sys.exit(1)

    start_time = time.time()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"))
            page = context.new_page()
            response = page.goto(url, timeout=45000)
            # wait for load to stabilize
            try:
                page.wait_for_load_state("load", timeout=30000)
            except Exception:
                pass

            load_time = time.time() - start_time
            status = response.status if response else None
            print(f"HTTP {status} returned for {url} (time: {load_time:.2f}s)")

            if status is None:
                print("No HTTP response object returned by Playwright; treating as failure.")
                if webhook_url:
                    send_slack_notification(webhook_url, f"❌ Smoke test failed: no response for {url} via Playwright.")
                sys.exit(1)

            if status >= 400:
                print("--- Response headers ---")
                try:
                    headers = response.headers
                    for k, v in headers.items():
                        print(f"{k}: {v}")
                except Exception:
                    pass
                try:
                    body = page.content() or ""
                    print("--- Response body (truncated) ---")
                    print(body[:1000])
                except Exception:
                    pass

                if webhook_url:
                    send_slack_notification(webhook_url, f"❌ Smoke test failed: HTTP {status} for {url} via Playwright.")
                else:
                    print("Slack webhook not configured; not sending failure notification.")
                context.close()
                browser.close()
                sys.exit(1)
            else:
                load_message = f"Page responded with {status} in {load_time:.2f} seconds (Playwright)."
                print("✅ Smoke check passed.")
                print(f"⏲️ {load_message}")
                if webhook_url:
                    send_slack_notification(webhook_url, load_message)

            context.close()
            browser.close()

    except Exception as e:
        print(f"Playwright error while requesting {url}: {e}")
        if webhook_url:
            send_slack_notification(webhook_url, f"❌ Playwright error while requesting {url}: {e}")
        else:
            print("Slack webhook not configured; not sending error notification.")
        sys.exit(1)

if __name__ == "__main__":
    url_to_check = os.environ.get("URL")
    # Treat empty string as not configured
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL") or None
    if not url_to_check:
        print("Error: Please provide the URL as environment variable 'URL'.")
        sys.exit(1)

    check_console_errors(url_to_check, webhook_url)
