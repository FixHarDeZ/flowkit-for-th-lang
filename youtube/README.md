# youtube/ — uploader

`upload.py` and `auth.py` are tracked. Everything under `channels/` is local-only
(gitignored) because it holds OAuth secrets and per-machine brand assets.

## One-time setup per channel

1. Google Cloud Console -> create/pick a project -> enable **YouTube Data API v3**
2. APIs & Services -> Credentials -> Create credentials -> **OAuth client ID**
   -> Application type: **Desktop app** -> download JSON
3. Save it as `youtube/channels/<channel>/client_secrets.json`
4. Copy `channels/channel_rules.template.json` to
   `channels/<channel>/channel_rules.json` and edit
5. Authorize (opens a browser once):

```bash
venv/bin/python youtube/auth.py <channel>
```

(Google API deps live in `venv`; plain `python3` will not have them. `venv/bin/pip` has a stale shebang from an old directory name — use `venv/bin/python -m pip install -r requirements.txt` instead.)

Writes `channels/<channel>/token.json`, refreshed automatically afterwards.
If consent screen is in "Testing" mode, add your own Google account under
Audience -> Test users, or the flow returns `access_denied`.

## Files per channel

```
youtube/channels/<channel>/
  client_secrets.json   OAuth client (you download it)
  token.json            auto-created, auto-refreshed
  channel_rules.json    upload rules + SEO defaults
  channel_info.json     auto-created by auth.py
  upload_history.json   auto-created by upload.py — drives max_per_day / min_gap
  <channel>_icon.png    used by /fk-brand-logo
```

## Quota

An upload costs 1600 units of the default 10,000/day quota — about 6 uploads per
day. `quotaExceeded` resets at midnight Pacific.
