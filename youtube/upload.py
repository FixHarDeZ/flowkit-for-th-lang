"""Rule-checked YouTube uploads for Flow Kit.

Public API (used by /fk-youtube-upload):
    detect_video_type(path)            -> ("short"|"long", "vertical"|"horizontal")
    load_channel_rules(channel)        -> dict (defaults merged in)
    validate_upload(channel, when, is_short) -> (ok, reason)
    auto_schedule(channel, count, is_short)  -> [iso8601 UTC, ...]
    upload_video(...)                  -> video_id
"""
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent.parent
CHANNELS_DIR = BASE_DIR / "youtube" / "channels"

DEFAULT_RULES = {
    "timezone": "Asia/Bangkok",
    "short": {
        "max_per_day": 3,
        "optimal_times": ["07:00", "12:00", "17:00"],
    },
    "long": {
        "max_per_day": 1,
        "optimal_times": ["19:00"],
    },
    "min_gap_hours": 4,
    "avoid_hours": [0, 1, 2, 3, 4, 5],
    "seo": {
        "title_max_chars": 65,
        "default_tags": [],
        "always_include_hashtags": [],
        "default_category": "22",
    },
}

# YouTube API limits
TITLE_MAX = 100
DESCRIPTION_MAX = 5000
TAGS_TOTAL_MAX = 500          # sum of tags, quoted tags cost +2
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB resumable chunks


# ─── channel config ──────────────────────────────────────────

def channel_dir(channel_name: str) -> Path:
    return CHANNELS_DIR / channel_name


def load_channel_rules(channel_name: str) -> dict:
    """Load channel_rules.json merged over DEFAULT_RULES. Missing file = defaults."""
    rules_file = channel_dir(channel_name) / "channel_rules.json"
    rules = json.loads(json.dumps(DEFAULT_RULES))  # deep copy
    if not rules_file.exists():
        print(f"WARNING: no {rules_file} — using defaults "
              f"(3 shorts/day, 4h gap, 07/12/17)")
        return rules
    user = json.loads(rules_file.read_text())
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(rules.get(key), dict):
            rules[key].update(value)
        else:
            rules[key] = value
    return rules


def _tz(rules: dict) -> ZoneInfo:
    return ZoneInfo(rules.get("timezone", "Asia/Bangkok"))


def _history_file(channel_name: str) -> Path:
    return channel_dir(channel_name) / "upload_history.json"


def load_history(channel_name: str) -> list[dict]:
    f = _history_file(channel_name)
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return []


def _append_history(channel_name: str, entry: dict) -> None:
    history = load_history(channel_name)
    history.append(entry)
    f = _history_file(channel_name)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(history, ensure_ascii=False, indent=2))


# ─── video inspection ────────────────────────────────────────

def detect_video_type(video_path: str) -> tuple[str, str]:
    """("short"|"long", "vertical"|"horizontal") — short = <61s AND vertical."""
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height", "-show_entries", "format=duration",
         "-of", "json", video_path],
        capture_output=True, text=True, timeout=60,
    )
    if probe.returncode != 0:
        raise RuntimeError(f"ffprobe failed for {video_path}: {probe.stderr[-200:]}")
    data = json.loads(probe.stdout)
    stream = data["streams"][0]
    width, height = int(stream["width"]), int(stream["height"])
    duration = float(data["format"]["duration"])
    orientation = "vertical" if height > width else "horizontal"
    video_type = "short" if duration < 61 and orientation == "vertical" else "long"
    return video_type, orientation


# ─── scheduling ──────────────────────────────────────────────

def _parse_when(when) -> datetime:
    if isinstance(when, datetime):
        dt = when
    else:
        dt = datetime.fromisoformat(str(when).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"schedule time needs a timezone offset: {when}")
    return dt


def validate_upload(channel_name: str, schedule_at, is_short: bool) -> tuple[bool, str]:
    """Check max_per_day, min_gap_hours and avoid_hours. Returns (ok, reason)."""
    rules = load_channel_rules(channel_name)
    tz = _tz(rules)
    when = _parse_when(schedule_at).astimezone(tz)
    kind = "short" if is_short else "long"
    limits = rules[kind]

    scheduled = []
    for entry in load_history(channel_name):
        if entry.get("type") != kind:
            continue
        stamp = entry.get("schedule_at") or entry.get("uploaded_at")
        if not stamp:
            continue
        try:
            scheduled.append(_parse_when(stamp).astimezone(tz))
        except ValueError:
            continue

    same_day = [d for d in scheduled if d.date() == when.date()]
    if len(same_day) >= limits["max_per_day"]:
        return False, (f"Max {limits['max_per_day']} {kind}s/day reached on "
                       f"{when:%Y-%m-%d}")

    gap = timedelta(hours=rules.get("min_gap_hours", 0))
    all_times = [_parse_when(e["schedule_at"] or e["uploaded_at"]).astimezone(tz)
                 for e in load_history(channel_name)
                 if e.get("schedule_at") or e.get("uploaded_at")]
    for other in all_times:
        if abs(when - other) < gap:
            return False, (f"Min gap {rules['min_gap_hours']}h not met "
                           f"(conflicts with {other:%Y-%m-%d %H:%M})")

    if when.hour in rules.get("avoid_hours", []):
        return False, f"{when:%H:%M} is inside avoid_hours {rules['avoid_hours']}"

    return True, "OK"


def auto_schedule(channel_name: str, count: int, is_short: bool) -> list[str]:
    """Pick the next `count` valid slots from the channel's optimal_times (UTC ISO)."""
    rules = load_channel_rules(channel_name)
    tz = _tz(rules)
    kind = "short" if is_short else "long"
    times = rules[kind]["optimal_times"]

    picked: list[str] = []
    now = datetime.now(tz)
    day = now.date()
    guard = 0

    while len(picked) < count and guard < 365:
        for slot in times:
            if len(picked) >= count:
                break
            hour, minute = (int(x) for x in slot.split(":"))
            when = datetime.combine(day, datetime.min.time(), tzinfo=tz).replace(
                hour=hour, minute=minute)
            if when <= now + timedelta(minutes=15):
                continue  # scheduledPublishTimeInPast guard
            ok, _ = validate_upload(channel_name, when, is_short)
            if not ok:
                continue
            if any(abs(when - _parse_when(p).astimezone(tz))
                   < timedelta(hours=rules.get("min_gap_hours", 0)) for p in picked):
                continue
            picked.append(when.astimezone(timezone.utc).isoformat().replace(
                "+00:00", "Z"))
        day += timedelta(days=1)
        guard += 1

    return picked


# ─── metadata guards ─────────────────────────────────────────

def _tags_cost(tags: list[str]) -> int:
    """YouTube counts quotes around tags containing spaces, plus separators."""
    if not tags:
        return 0
    return sum(len(t) + (2 if " " in t else 0) for t in tags) + (len(tags) - 1)


def trim_tags(tags: list[str], budget: int = TAGS_TOTAL_MAX) -> list[str]:
    """Drop tags from the end until the quoted total fits YouTube's 500-char cap."""
    kept = list(tags)
    while kept and _tags_cost(kept) > budget:
        kept.pop()
    return kept


# ─── upload ──────────────────────────────────────────────────

def upload_video(
    channel_name: str,
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[list[str]] = None,
    category_id: str = "22",
    schedule_at: Optional[str] = None,
    is_short: bool = True,
    made_for_kids: bool = False,
    dry_run: bool = False,
) -> str:
    """Upload one video (resumable, 10MB chunks). Returns the YouTube video id."""
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    from youtube.auth import get_credentials

    path = Path(video_path)
    if not path.exists():
        raise FileNotFoundError(video_path)

    if is_short and "#shorts" not in title.lower():
        title = f"{title[:TITLE_MAX - len(' #Shorts')]} #Shorts"
    title = title[:TITLE_MAX]
    description = description[:DESCRIPTION_MAX]
    tags = trim_tags(tags or [])

    status: dict = {"selfDeclaredMadeForKids": made_for_kids}
    if schedule_at:
        when = _parse_when(schedule_at).astimezone(timezone.utc)
        if when <= datetime.now(timezone.utc):
            raise ValueError(f"scheduledPublishTimeInPast: {schedule_at}")
        status["privacyStatus"] = "private"
        status["publishAt"] = when.isoformat().replace("+00:00", "Z")
    else:
        status["privacyStatus"] = "public"

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": status,
    }

    if dry_run:
        print(json.dumps({"would_upload": str(path), "body": body},
                         ensure_ascii=False, indent=2))
        return ""

    creds = get_credentials(channel_name, interactive=False)
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    media = MediaFileUpload(str(path), chunksize=CHUNK_SIZE, resumable=True,
                            mimetype="video/mp4")
    request = yt.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    try:
        while response is None:
            progress, response = request.next_chunk()
            if progress:
                print(f"  upload {int(progress.progress() * 100):3d}%")
    except HttpError as e:
        raise RuntimeError(f"YouTube API error {e.resp.status}: {e.content}") from e

    video_id = response["id"]
    video_type = "short" if is_short else "long"
    _append_history(channel_name, {
        "video_id": video_id,
        "file": str(path),
        "title": title,
        "type": video_type,
        "schedule_at": status.get("publishAt"),
        "uploaded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "url": (f"https://youtube.com/shorts/{video_id}" if is_short
                else f"https://youtu.be/{video_id}"),
    })
    return video_id
