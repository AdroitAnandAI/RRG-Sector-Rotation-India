"""
Helper to generate a Zerodha Kite Connect access token.

Kite access tokens expire every day, so you need to run this once per day
(after market login) to refresh KITE_ACCESS_TOKEN in your .env file.

Prerequisites in .env (or environment):
    KITE_API_KEY=...
    KITE_API_SECRET=...

Usage:
    python kite_login.py

Steps it walks you through:
    1. Opens (prints) the Kite login URL.
    2. You log in; Kite redirects to your app's redirect URL with a
       `request_token=...` query parameter.
    3. Paste that request_token back here.
    4. The script prints the access_token and, if a .env file exists, offers
       to update KITE_ACCESS_TOKEN in it automatically.
"""
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from kiteconnect import KiteConnect

load_dotenv()

ENV_PATH = Path(__file__).with_name(".env")


def update_env_access_token(token: str) -> bool:
    """Write/replace KITE_ACCESS_TOKEN in the local .env file. Returns True on success."""
    if not ENV_PATH.exists():
        return False
    text = ENV_PATH.read_text(encoding="utf-8")
    line = f"KITE_ACCESS_TOKEN={token}"
    if re.search(r"^KITE_ACCESS_TOKEN=.*$", text, flags=re.MULTILINE):
        text = re.sub(r"^KITE_ACCESS_TOKEN=.*$", line, text, flags=re.MULTILINE)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += line + "\n"
    ENV_PATH.write_text(text, encoding="utf-8")
    return True


def main():
    api_key = os.getenv("KITE_API_KEY", "").strip()
    api_secret = os.getenv("KITE_API_SECRET", "").strip()

    if not api_key or not api_secret:
        print("ERROR: Set KITE_API_KEY and KITE_API_SECRET in your .env file first.")
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)

    print("\n1) Open this URL in your browser and log in:\n")
    print("   " + kite.login_url())
    print("\n2) After login you'll be redirected to your app's redirect URL, e.g.:")
    print("   https://your-redirect-url/?request_token=XXXXXX&action=login&status=success")
    print("\n3) Copy the value of request_token from that URL.\n")

    request_token = input("Paste request_token here: ").strip()
    if not request_token:
        print("ERROR: No request_token provided.")
        sys.exit(1)

    try:
        data = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as e:
        print(f"ERROR: Failed to generate session: {e}")
        sys.exit(1)

    access_token = data["access_token"]
    print("\nSUCCESS! Your access token is:\n")
    print("   " + access_token + "\n")

    if update_env_access_token(access_token):
        print(f"Updated KITE_ACCESS_TOKEN in {ENV_PATH}")
    else:
        print("No .env file found to update. Add this line to your .env manually:")
        print(f"   KITE_ACCESS_TOKEN={access_token}")


if __name__ == "__main__":
    main()
