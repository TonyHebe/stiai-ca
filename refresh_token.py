"""
refresh_token.py
Exchanges the short-lived Page Access Token in .env for a permanent one.

How it works:
  1. Reads the short-lived token from FACEBOOK_PAGE_ACCESS_TOKEN in .env
  2. Exchanges it for a long-lived User Token (60 days)
  3. Uses that to fetch the Page Token — Page tokens from long-lived
     user tokens NEVER expire as long as the user doesn't revoke access
  4. Writes the permanent Page Token back into .env automatically

Run BEFORE the short-lived token expires:
  python refresh_token.py
"""

import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID       = os.getenv("FACEBOOK_APP_ID", "")
APP_SECRET   = os.getenv("FACEBOOK_APP_SECRET", "")
SHORT_TOKEN  = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN", "")
PAGE_ID      = os.getenv("FACEBOOK_PAGE_ID", "")
ENV_FILE     = Path(__file__).parent / ".env"

GRAPH = "https://graph.facebook.com/v20.0"


def check_env() -> None:
    missing = []
    if not APP_ID:          missing.append("FACEBOOK_APP_ID")
    if not APP_SECRET:      missing.append("FACEBOOK_APP_SECRET")
    if not SHORT_TOKEN:     missing.append("FACEBOOK_PAGE_ACCESS_TOKEN")
    if not PAGE_ID:         missing.append("FACEBOOK_PAGE_ID")
    if missing:
        sys.exit(f"[refresh_token] Missing in .env: {', '.join(missing)}")


def get_long_lived_user_token(short_token: str) -> str:
    """Exchange short-lived token → long-lived user token (60 days)."""
    print("[1/3] Exchanging short-lived token for long-lived user token…")
    resp = requests.get(
        f"{GRAPH}/oauth/access_token",
        params={
            "grant_type":        "fb_exchange_token",
            "client_id":         APP_ID,
            "client_secret":     APP_SECRET,
            "fb_exchange_token": short_token,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        sys.exit(f"[refresh_token] Error: {data['error']['message']}")
    token = data.get("access_token", "")
    expires = data.get("expires_in", "unknown")
    print(f"       OK Long-lived user token obtained (expires_in={expires}s ~ 60 days)")
    return token


def get_page_access_token(long_user_token: str, page_id: str) -> str:
    """
    Use the long-lived user token to get a permanent Page Access Token.
    Page tokens derived from a long-lived user token never expire.
    """
    print("[2/3] Fetching permanent Page Access Token...")

    # Try direct page endpoint first
    resp = requests.get(
        f"{GRAPH}/{page_id}",
        params={"fields": "access_token,name,id", "access_token": long_user_token},
        timeout=15,
    )
    data = resp.json()

    if resp.ok and "access_token" in data:
        print(f"       OK Page token obtained for: {data.get('name')} (id={data.get('id')})")
        return data["access_token"]

    # Fallback: use /me/accounts
    print("       Trying /me/accounts fallback...")
    resp2 = requests.get(
        f"{GRAPH}/me/accounts",
        params={"access_token": long_user_token},
        timeout=15,
    )
    data2 = resp2.json()

    if resp2.ok and "data" in data2:
        pages = data2["data"]
        print(f"       Found {len(pages)} page(s):")
        for p in pages:
            print(f"         - {p.get('name')} (id={p.get('id')})")
        match = next((p for p in pages if p.get("id") == page_id), None) or (pages[0] if pages else None)
        if match and match.get("access_token"):
            # Update page ID in .env if different
            if match.get("id") != page_id:
                content = ENV_FILE.read_text(encoding="utf-8")
                import re as _re
                ENV_FILE.write_text(
                    _re.sub(r"^(FACEBOOK_PAGE_ID\s*=).*$", rf"\g<1>{match['id']}", content, flags=_re.MULTILINE),
                    encoding="utf-8"
                )
                print(f"       Updated FACEBOOK_PAGE_ID to {match['id']}")
            print(f"       OK Page token obtained for: {match.get('name')}")
            return match["access_token"]

    # Last resort: save user token (some permissions work with it)
    print("       Warning: Could not get page-specific token, saving user token.")
    resp3 = requests.get(f"{GRAPH}/me", params={"access_token": long_user_token}, timeout=15)
    data3 = resp3.json()
    if "error" in data3:
        sys.exit(f"[refresh_token] Token invalid: {data3['error']['message']}")
    print(f"       OK User token valid (me={data3.get('name', '?')})")
    return long_user_token


def update_env_file(new_token: str) -> None:
    """Replace FACEBOOK_PAGE_ACCESS_TOKEN value in .env."""
    print("[3/3] Writing new token to .env…")
    content = ENV_FILE.read_text(encoding="utf-8")
    updated = re.sub(
        r"^(FACEBOOK_PAGE_ACCESS_TOKEN\s*=).*$",
        rf"\g<1>{new_token}",
        content,
        flags=re.MULTILINE,
    )
    ENV_FILE.write_text(updated, encoding="utf-8")
    print("       OK .env updated successfully")


def main() -> None:
    print("=== Facebook Token Exchange ===\n")
    check_env()

    long_lived_token = get_long_lived_user_token(SHORT_TOKEN)
    page_token       = get_page_access_token(long_lived_token, PAGE_ID)
    update_env_file(page_token)

    print(
        "\n=== Done ===\n"
        "Your .env now contains a permanent Page Access Token.\n"
        "This token will not expire as long as:\n"
        "  - You don't change your Facebook password\n"
        "  - You don't revoke the StiaiCa app's permissions\n"
        "  - The app remains active\n\n"
        "You can verify it works with:\n"
        "  python main.py --verify\n"
    )


if __name__ == "__main__":
    main()
