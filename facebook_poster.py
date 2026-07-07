"""
facebook_poster.py
Posts a photo + caption to a Facebook Page via the Graph API v20.0.
Requires a long-lived Page Access Token with pages_manage_posts
and pages_read_engagement permissions.
"""

import os
import requests

GRAPH_API_VERSION = "v20.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def post_photo_to_page(
    page_id: str,
    access_token: str,
    image_path: str,
    caption: str,
    published: bool = True,
) -> dict:
    """
    Upload *image_path* and publish it on the Facebook Page as a photo post.

    Args:
        page_id:       Numeric Facebook Page ID.
        access_token:  Long-lived Page Access Token.
        image_path:    Local path to the JPEG image.
        caption:       Post description / caption text.
        published:     If False the post is saved as a draft (useful for testing).

    Returns:
        Facebook API response dict containing at minimum {"post_id": "...", "id": "..."}.

    Raises:
        requests.HTTPError on API failure.
    """
    url = f"{GRAPH_BASE}/{page_id}/photos"

    with open(image_path, "rb") as image_file:
        response = requests.post(
            url,
            data={
                "message":     caption,
                "published":   str(published).lower(),
                "access_token": access_token,
            },
            files={"source": (os.path.basename(image_path), image_file, "image/jpeg")},
            timeout=60,
        )

    if not response.ok:
        _handle_api_error(response)

    result = response.json()
    print(f"[facebook_poster] Posted successfully → post_id={result.get('post_id') or result.get('id')}")
    return result


def _handle_api_error(response: requests.Response) -> None:
    """Parse Facebook error payload and raise a descriptive exception."""
    try:
        err = response.json().get("error", {})
        msg = f"Facebook API error {err.get('code')}: {err.get('message')} (type={err.get('type')})"
    except Exception:
        msg = f"HTTP {response.status_code}: {response.text[:400]}"
    raise requests.HTTPError(msg, response=response)


def verify_credentials(page_id: str, access_token: str) -> bool:
    """
    Quick sanity-check: fetches the page name to confirm the token is valid.
    Returns True on success, prints error and returns False otherwise.
    """
    url   = f"{GRAPH_BASE}/{page_id}"
    resp  = requests.get(url, params={"fields": "name,id", "access_token": access_token}, timeout=10)
    if resp.ok:
        data = resp.json()
        print(f"[facebook_poster] Token OK — page: {data.get('name')} (id={data.get('id')})")
        return True
    else:
        print(f"[facebook_poster] Token check FAILED: {resp.text[:200]}")
        return False
