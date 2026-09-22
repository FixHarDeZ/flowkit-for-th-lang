"""OAuth2 (installed-app flow) for a single channel.

Usage:
    python3 youtube/auth.py <channel_name>

Reads  youtube/channels/<channel>/client_secrets.json  (you create this in
Google Cloud: APIs & Services -> Credentials -> OAuth client -> Desktop app)
Writes youtube/channels/<channel>/token.json           (auto-refreshed later)
"""
import json
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]

BASE_DIR = Path(__file__).resolve().parent.parent
CHANNELS_DIR = BASE_DIR / "youtube" / "channels"


def channel_dir(channel_name: str) -> Path:
    return CHANNELS_DIR / channel_name


def get_credentials(channel_name: str, interactive: bool = True) -> Credentials:
    """Return valid credentials for a channel, refreshing or prompting as needed."""
    cdir = channel_dir(channel_name)
    secrets = cdir / "client_secrets.json"
    token_file = cdir / "token.json"

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            token_file.write_text(creds.to_json())
            return creds
        except Exception as e:
            # invalid_grant -> token revoked; fall through to a fresh consent
            if not interactive:
                raise RuntimeError(
                    f"token refresh failed for '{channel_name}' ({e}). "
                    f"Run: python3 youtube/auth.py {channel_name}"
                ) from e

    if not interactive:
        raise RuntimeError(
            f"No valid token for '{channel_name}'. "
            f"Run: python3 youtube/auth.py {channel_name}"
        )

    if not secrets.exists():
        raise FileNotFoundError(
            f"Missing {secrets}\n"
            "Create an OAuth client (type: Desktop app) in Google Cloud Console, "
            "download the JSON, and save it at that path."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets), SCOPES)
    creds = flow.run_local_server(port=0)
    cdir.mkdir(parents=True, exist_ok=True)
    token_file.write_text(creds.to_json())
    return creds


def fetch_channel_info(channel_name: str) -> dict:
    """Store basic channel stats so later steps can show which account is wired up."""
    from googleapiclient.discovery import build

    creds = get_credentials(channel_name)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    resp = yt.channels().list(part="snippet,statistics", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError("No channel found for these credentials")
    item = items[0]
    info = {
        "channel_id": item["id"],
        "title": item["snippet"]["title"],
        "subscribers": item["statistics"].get("subscriberCount"),
        "videos": item["statistics"].get("videoCount"),
    }
    out = channel_dir(channel_name) / "channel_info.json"
    out.write_text(json.dumps(info, ensure_ascii=False, indent=2))
    return info


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 youtube/auth.py <channel_name>")
        raise SystemExit(2)
    name = sys.argv[1]
    get_credentials(name)
    try:
        info = fetch_channel_info(name)
        print(f"Authorized: {info['title']} ({info['channel_id']}) "
              f"— {info['subscribers']} subs, {info['videos']} videos")
    except Exception as e:
        print(f"Token saved, but channel lookup failed: {e}")
    print(f"Token: youtube/channels/{name}/token.json")
