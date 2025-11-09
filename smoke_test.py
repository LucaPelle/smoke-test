import os
import sys
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def send_slack_notification(webhook_url, message):
    if not webhook_url:
        print("Slack webhook not configured; skipping Slack notification.")
        return

    payload = {"text": message}
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending Slack notification: {e}")

def check_console_errors(url, webhook_url):
    # Use requests to perform a simple HTTP smoke-check (no JS execution).
    # Note: requests cannot capture browser console logs or take screenshots.
    session = requests.Session()
    retries = Retry(total=2, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))

    start_time = time.time()
    # Use a browser-like User-Agent to reduce chance of simple bot-blocking
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = session.get(url, headers=headers, timeout=30)
        load_time = time.time() - start_time

        status = resp.status_code
        print(f"HTTP {status} returned for {url} (time: {load_time:.2f}s)")

        if status >= 400:
            error_message = f"❌ Smoke test failed: HTTP {status} for {url}."
            # Print some diagnostic information to help debug 403/blocks
            print("--- Response headers ---")
            for k, v in resp.headers.items():
                print(f"{k}: {v}")
            print("--- Response body (truncated) ---")
            body = resp.text or ""
            print(body[:1000])

            if webhook_url:
                send_slack_notification(webhook_url, error_message)
            else:
                print("Slack webhook not configured; not sending failure notification.")
            sys.exit(1)
        else:
            load_message = f"Page responded with {status} in {load_time:.2f} seconds."
            print("✅ Smoke check passed.")
            print(f"⏲️ {load_message}")
            if webhook_url:
                send_slack_notification(webhook_url, load_message)

    except requests.exceptions.RequestException as e:
        print(f"Error while requesting {url}: {e}")
        if webhook_url:
            send_slack_notification(webhook_url, f"❌ Error while requesting {url}: {e}")
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
