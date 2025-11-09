import os
import sys
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def send_slack_notification(webhook_url, message):
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
    try:
        resp = session.get(url, timeout=30)
        load_time = time.time() - start_time

        status = resp.status_code
        print(f"HTTP {status} returned for {url} (time: {load_time:.2f}s)")

        if status >= 400:
            error_message = f"❌ Smoke test failed: HTTP {status} for {url}."
            send_slack_notification(webhook_url, error_message)
            sys.exit(1)
        else:
            load_message = f"Page responded with {status} in {load_time:.2f} seconds."
            print("✅ Smoke check passed.")
            print(f"⏲️ {load_message}")
            send_slack_notification(webhook_url, load_message)

    except requests.exceptions.RequestException as e:
        print(f"Error while requesting {url}: {e}")
        send_slack_notification(webhook_url, f"❌ Error while requesting {url}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    url_to_check = os.environ.get("URL")
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if url_to_check is None or webhook_url is None:
        print("Error: Please provide both the URL and the Slack webhook URL as environment variables.")
        sys.exit(1)  # Exit with non-zero status code to indicate failure
    else:
        check_console_errors(url_to_check, webhook_url)
