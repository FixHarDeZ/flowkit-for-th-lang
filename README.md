<p align="center">
  <img src="docs/images/flowkit_banner.svg" width="720" alt="FLOW KIT — Thai Language Edition" />
</p>

<p align="center">
  <a href="#license"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"/></a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white" alt="Python 3.10+"/>
  <img src="https://img.shields.io/badge/Chrome-MV3-4285F4?logo=googlechrome&logoColor=white" alt="Chrome MV3"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/ffmpeg-required-007808?logo=ffmpeg&logoColor=white" alt="ffmpeg"/>
  <a href="CLAUDE.md"><img src="https://img.shields.io/badge/Docs-CLAUDE.md-8A2BE2" alt="Documentation"/></a>
</p>

---

# FlowKit — Thai Language Video Production

ระบบสร้างวิดีโอ AI ผ่าน Google Flow สำหรับทำคลิปภาษาไทยโดยเฉพาะ ดัดแปลงจาก [FlowKit](https://github.com/tuannguyenhoangit-droid/google-flow-agent) ของ tuannguyenhoangit-droid

ใช้ Chrome Extension เป็นตัวกลางเชื่อมต่อกับ Google Flow — สร้าง reCAPTCHA และรัน batchexecute RPC ผ่าน tab ที่ sign in ไว้ที่ `flow.google.com`

## จุดเด่นของเวอร์ชันภาษาไทย

- **TTS ภาษาไทย** — OmniVoice รองรับ 600+ ภาษา รวมถึงไทย พร้อม voice cloning
- **Narrator ภาษาไทย** — สร้างบทบรรยาย + voice-over อัตโนมัติ
- **Text Overlays ภาษาไทย** — ใส่ข้อความภาษาไทยบนวิดีโอ
- **SEO ภาษาไทย** — Generate title, description, tags, hashtags สำหรับ YouTube ภาษาไทย
- **Fact-check ก่อนเขียนบท** — ตรวจสอบข้อมูลก่อนทำคลิป

---

## Showcase

ตัวอย่างคลิปที่สร้างจากipelines นี้ทั้งหมด — จากไอเดีย ถึง YouTube-ready

### Pipeline Output

| Output | คำอธิบาย |
|--------|---------|
| Reference images | ตัวละคร/สถานที่ หนึ่งตัวต่อรูป — รักษาความสม่ำเสมอ |
| Scene images | .compose แต่ละ scene โดยใช้ reference images |
| 8-second video clips | สร้างจาก scene images พร้อม camera motion |
| 4K upscale | Upscale เป็น 4K (optional) |
| Narrator TTS | Voice-cloned narration ต่อ scene |
| Final video | รวมคลิปทั้งหมด + ตัดตาม duration ของ narrator |
| Thumbnails | YouTube-optimized พร้อม text overlays + branding |
| YouTube metadata | SEO-optimized title, description, tags, hashtags |

---

## Architecture

```
┌──────────────────┐     WebSocket      ┌──────────────────────┐     ┌──────────────────┐
│  Python Agent    │◄──────────────────►│  Chrome Extension     │────►│  flow.google.com │
│  (FastAPI+SQLite)│    localhost:9222  │  (MV3 Service Worker) │     │  (signed-in tab) │
│                  │                    │                       │     │                  │
│  - REST API :8100│  ── envelopes ──►  │  - reCAPTCHA mint     │     │  batchexecute    │
│  - Queue worker  │  ◄── responses ──  │  - runs the RPC in    │     │  cookie + `at`   │
│  - Post-process  │                    │    the page's world   │     │                  │
│  - SQLite DB     │                    │                       │     │                  │
└──────────────────┘                    └──────────────────────┘     └──────────────────┘
```

Flow sign ทุก call ด้วย session cookie + per-page `at` token, reCAPTCHA ใช้ครั้งเดียว ไม่สามารถ replay จากข้างนอกได้ ต้องเปิด tab Flow ค้างไว้

---

## Quick Start

### One-command setup

```bash
./setup.sh
```

ตรวจสอบและติดตั้ง: Python 3.10+, pip, ffmpeg, ffprobe, Chrome, สร้าง venv, ติดตั้ง dependencies

### Manual setup

```bash
pip install -r requirements.txt
```

### Run

```bash
# 1. Load Chrome extension: chrome://extensions → Developer mode → Load unpacked → extension/
# 2. Open https://flow.google.com/ and sign in — leave the tab open
# 3. Create a project in the Flow UI and copy its uuid out of the URL
export FLOW_PROJECT_ID=<that uuid>

# 4. Start agent
source venv/bin/activate
python -m agent.main

# 5. Verify
curl http://127.0.0.1:8100/health
# {"status":"ok","extension_connected":true}
```

`flow_key_present: false` เป็นเรื่องปกติ — transport ปัจจุบันไม่ใช้ bearer token แล้ว

### Configuration

| Env var | Default | คำอธิบาย |
|---------|---------|--------|
| `FLOW_PROJECT_ID` | — | Flow project ที่ทุก RPC อ้างถึง **จำเป็น** |
| `FLOW_ALLOW_DEGRADED` | `0` | `1` ให้ scene chaining fallback เป็น plain i2v |
| `DEFAULT_PAYGATE_TIER` | `PAYGATE_TIER_TWO` | ใช้สำหรับ DB + dashboard |

---

## End-to-End Example: คลิปสารคดีสั้น

ตัวอย่าง: คลิปสารคดี 3 ฉาก แนวตั้ง สไตล์ realistic

### Mental Model

ระบบใช้ **reference images** รักษาความสม่ำเสมอ:

1. **Identify องค์ประกอบภาพ** ที่ต้องเหมือนกันทุกฉาก:
   - ตัวละคร → `entity_type: "character"` (portrait reference)
   - สถานที่ → `entity_type: "location"` (landscape reference)
   - สิ่งของสำคัญ → `entity_type: "visual_asset"` (detail reference)

2. **เขียน description เฉพาะรูปลักษณ์** — ใช้สร้าง reference image:
   - `"ชุดข้าราชการสีกากี หมวกกลัดเข็มขัด ผิวสองสี"`

3. **เขียน scene prompts เป็น ACTION** — อ้างชื่อ entity, บอกว่าทำอะไร:
   - `"ข้าราชการยืนที่ตึกชูมือปราศัย"` ไม่ใช่ `"ชายในชุดสีกากียืน..."`

4. **ใส่ชื่อ entity ทุกตัว** ใน `character_names` array

### Using Skills (recommended)

```
/fk-create-project             ← ถามเรื่องเรื่อง, สร้าง entities + scenes
/fk-research "หัวข้อ"          ← ตรวจสอบข้อมูลก่อนเขียนบท
/fk-gen-refs <project_id>      ← สร้าง reference images ทุก entity
/fk-gen-images <pid> <vid>     ← สร้าง scene images
/fk-gen-videos <pid> <vid>     ← สร้างวิดีโอ (2-5 นาทีต่อ scene)
/fk-gen-narrator               ← สร้างบทบรรยาย + TTS ภาษาไทย
/fk-concat-fit-narrator        ← ตัดคลิปตาม duration narrator + concat
/fk-youtube-seo                ← สร้าง metadata สำหรับ YouTube ภาษาไทย
/fk-youtube-upload             ← อัปโหลดขึ้น YouTube
```

Full pipeline ใน 7 คำสั่ง

---

## Core Concepts

### Reference Image System

| Entity Type | Aspect Ratio | Composition |
|-------------|-------------|-------------|
| `character` | Portrait | Full body หัวจรดเท้า, หันหน้าตรง, centered |
| `location` | Landscape | Establishing shot, level horizon |
| `creature` | Portrait | Full body, ท่าทางธรรมชาติ |
| `visual_asset` | Portrait | มุมมองละเอียด, เนื้อสัมผัส |

### Scene Prompts = Action Only

```
ถูก:   "ข้าราชการเดินปราศัยที่ลานกว้าง ผู้คนปรบมือ"
ผิด:   "ชายในชุดข้าราชการสีกากีเดินปราศัยที่ลานกว้าง..."
```

### Media ID = UUID

ทุก `media_id` เป็น UUID format (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`) ไม่ใช่ `CAMS...`

### Two Prompts per Scene

- `prompt` — บรรยายภาพนิ่ง (frame 0)
- `video_prompt` — บรรยาย motion 8 วินาที พร้อม sub-clip timing:

```
0-3s: กว้าง กล้องเลื่อนลง ตัวละครเดินออกมาจากสถานที่ ตัวละครพูด "สวัสดีครับ"
3-6s: มุมต่ำ tracking shot ตัวละครเดินข้ามลาน ตัวละครพูด "วันนี้อากาศดี"
6-8s: ตัวละครมองกล้อง ยิ้ม golden hour backlight เงียบ ambient เสียงลม
```

---

## Skills (AI Agent Workflows)

### Basic Pipeline

| Skill | คำอธิบาย |
|-------|---------|
| `/fk-create-project` | สร้าง project + entities + scenes interactively |
| `/fk-research` | Fact-check ก่อนเขียนบท |
| `/fk-gen-refs` | สร้าง reference images ทุก entity |
| `/fk-gen-images` | สร้าง scene images พร้อม character refs |
| `/fk-gen-videos` | สร้างวิดีโอจาก scene images |
| `/fk-concat` | Download + merge วิดีโอทั้งหมด |
| `/fk-pipeline` | Smart full-pipeline orchestrator |
| `/fk-monitor` | Live monitor สำหรับ pipeline |

### Advanced Video

| Skill | คำอธิบาย |
|-------|---------|
| `/fk-gen-chain-videos` | Auto start+end frame chaining |
| `/fk-insert-scene` | Multi-angle shots, cutaways |
| `/fk-creative-mix` | Analyze story + suggest techniques |

### Review & Quality

| Skill | คำอธิบาย |
|-------|---------|
| `/fk-review-video` | AI vision scoring คุณภาพวิดีโอ |
| `/fk-review-board` | Visual scene-by-scene review |
| `/fk-change-provider` | เปลี่ยน AI CLI/model สำหรับ review |

### TTS & Narration (สำคัญสำหรับคลิปภาษาไทย)

| Skill | คำอธิบาย |
|-------|---------|
| `/fk-gen-tts-template` | สร้าง voice template สำหรับ narration |
| `/fk-import-voice` | Import voice recording มีอยู่แล้ว |
| `/fk-gen-narrator` | สร้างบทบรรยาย + TTS ทุก scene |
| `/fk-gen-text-overlays` | ใส่ข้อความภาษาไทยบนวิดีโอ |
| `/fk-concat-fit-narrator` | ตัดคลิปตาม duration ของ narrator |
| `/fk-gen-music` | สร้างเพลงประกอบผ่าน Suno |

### YouTube

| Skill | คำอธิบาย |
|-------|---------|
| `/fk-youtube-seo` | สร้าง SEO metadata ภาษาไทย |
| `/fk-brand-logo` | ใส่ channel icon watermark |
| `/fk-youtube-upload` | อัปโหลดขึ้น YouTube |
| `/fk-thumbnail` | สร้าง YouTube thumbnails |

### Utilities

| Skill | คำอธิบาย |
|-------|---------|
| `/fk-status` | Project status dashboard |
| `/fk-switch-project` | เปลี่ยน active project |
| `/fk-fix-uuids` | แก้ไข media_ids ที่ไม่ใช่ UUID |
| `/fk-refresh-urls` | Refresh expired signed URLs |
| `/fk-upload-image` | Upload image → ได้ media_id |
| `/fk-add-material` | ตั้งค่า image material style |
| `/fk-change-model` | เปลี่ยน video/image model |
| `/fk-doctor` | Diagnose ทุก error + บอกวิธีแก้ |

---

## Video Generation Techniques

| Technique | API Type | Use Case |
|-----------|----------|----------|
| **i2v** | `GENERATE_VIDEO` | Image → video (standard) |
| **i2v_fl** | `GENERATE_VIDEO` + endImage | Start+end frame → smooth transitions |
| **r2v** | `GENERATE_VIDEO_REFS` | Reference images → video |
| **Upscale** | `UPSCALE_VIDEO` | Video → 4K (TIER_TWO only) |

---

## TTS Narration — OmniVoice (สำคัญสำหรับคลิปไทย)

Voice-cloned narration สำหรับแต่ละ scene ใช้ [OmniVoice](https://github.com/tuannguyenhoangit-droid/OmniVoice) — รองรับ 600+ ภาษา รวมถึงภาษาไทย

### Setup

```bash
pip install torch==2.8.0 torchaudio==2.8.0
pip install omnivoice
python3 -c "from omnivoice import OmniVoice; print('OK')"
```

ถ้า OmniVoice อยู่คนละ venv:
```bash
export TTS_PYTHON_BIN=/path/to/omnivoice-venv/bin/python3
```

### Workflow

1. **สร้าง voice template** — `/fk-gen-tts-template` — สร้าง anchor voice WAV
2. **เพิ่ม narrator text** แต่ละ scene — `PATCH /api/scenes/{id}` with `narrator_text`
3. **สร้าง narration** — `/fk-gen-narrator` — voice-clone template ทุก scene
4. **Concat with narration** — `/fk-concat-fit-narrator` — ตัดคลิปตาม TTS duration

CPU-only recommended. ~15-30s ต่อ scene

---

## YouTube Upload Pipeline

### Setup

```bash
# 1. Place OAuth credentials
cp client_secrets.json youtube/channels/<channel_name>/

# 2. Authenticate
python3 youtube/auth.py <channel_name>

# 3. Token saved to youtube/channels/<channel_name>/token.json
```

### Skill Chain

```
/fk-youtube-seo    → สร้าง title, description, hashtags, tags (ภาษาไทย)
/fk-brand-logo     → ใส่ channel icon watermark
/fk-youtube-upload  → validate rules + upload (auto-detect Short vs Long-form)
```

---

## API Reference

### CRUD Endpoints

| Resource | Create | List | Get | Update | Delete |
|----------|--------|------|-----|--------|--------|
| Project | `POST /api/projects` | `GET /api/projects` | `GET /api/projects/{id}` | `PATCH /api/projects/{id}` | `DELETE /api/projects/{id}` |
| Character | `POST /api/characters` | `GET /api/characters` | `GET /api/characters/{id}` | `PATCH /api/characters/{id}` | `DELETE /api/characters/{id}` |
| Video | `POST /api/videos` | `GET /api/videos?project_id=` | `GET /api/videos/{id}` | `PATCH /api/videos/{id}` | `DELETE /api/videos/{id}` |
| Scene | `POST /api/scenes` | `GET /api/scenes?video_id=` | `GET /api/scenes/{id}` | `PATCH /api/scenes/{id}` | `DELETE /api/scenes/{id}` |
| Request | `POST /api/requests` | `GET /api/requests` | `GET /api/requests/{id}` | `PATCH /api/requests/{id}` | — |

### Special Endpoints

| Endpoint | คำอธิบาย |
|----------|---------|
| `GET /health` | Server + extension status |
| `GET /api/flow/status` | Extension connection details |
| `GET /api/requests/pending` | Pending request queue |

### Request Types

| Type | Required Fields | Async? | reCAPTCHA? |
|------|----------------|--------|------------|
| `GENERATE_CHARACTER_IMAGE` | character_id, project_id | No | Yes |
| `GENERATE_IMAGE` | scene_id, project_id, video_id, orientation | No | Yes |
| `GENERATE_VIDEO` | scene_id, project_id, video_id, orientation | Yes | Yes |
| `GENERATE_VIDEO_REFS` | scene_id, project_id, video_id, orientation | Yes | Yes |
| `UPSCALE_VIDEO` | scene_id, project_id, video_id, orientation | Yes | Yes |

---

## Worker Behavior

- **Server handles throttling** — max 5 concurrent + 10s cooldown อัตโนมัติ ใช้ `POST /api/requests/batch`
- **Reference blocking** — สร้าง scene image ไม่ได้ถ้า entity ยังไม่มี `media_id`
- **Skip completed** — ไม่ generate ซ้ำ
- **Cascade clear** — regenerate image ล้าง downstream video + upscale
- **Retry** — สูงสุด 5 ครั้ง พร้อม exponential backoff
- **UUID enforcement** — ดึง UUID จาก fifeUrl ถ้า response ไม่ให้
- **Voice context** — ต่อ `voice_description` ต่อท้าย video prompt อัตโนมัติ
- **No background music** — ต่อ "no background music, keep sound effects" อัตโนมัติ

---

## Error Handling

### Flow-Native Structured Errors

| Reason | ความหมาย | จัดการอย่างไร |
|--------|---------|-------------|
| `PUBLIC_ERROR_UNSAFE_GENERATION` | Prompt โดน safety filter | FAILED — เขียน prompt ใหม่ |
| `PUBLIC_ERROR_USER_QUOTA_REACHED` | Credits หมดวัน | FAILED — รอ reset |
| `PUBLIC_ERROR_MODEL_ACCESS_DENIED` | Tier mismatch | FAILED — ควร downgrade model |
| `Requested entity was not found` | media_id หมดอายุ (~1h) | Auto-recover — re-upload แล้ว re-queue |
| `Internal error encountered` | Flow transient 500 | Exponential backoff retry |
| `reCAPTCHA failed` / `captcha` | Extension แก้ CAPTCHA ไม่ได้ | Retry สูงสุด 10x |

### Common Symptoms → Fix

| ปัญหา | วิธีแก้ |
|--------|---------|
| Extension "Agent disconnected" | Start `python -m agent.main` |
| Extension "No token" | ปกติ — batch path ไม่ใช้ bearer แล้ว |
| `CAPTCHA_FAILED: NO_FLOW_TAB` | เปิด Google Flow tab |
| `media_id` เริ่มต้นด้วย `CAMS...` | รัน `/fk-fix-uuids` |
| Upscale "permission denied" | ต้องใช้ `PAYGATE_TIER_TWO` |
| Request stuck PROCESSING | ตรวจ `error_message`; ถ้า extension หลุด restart |

---

## AI CLI Compatibility

| CLI | Instructions | วิธีใช้ Skills |
|-----|-------------|-------------|
| Claude Code | `CLAUDE.md` (auto-loaded) | Native `/fk-*` slash commands |
| Codex CLI | `AGENTS.md` → reads `CLAUDE.md` | Agent อ่าน `skills/fk-<name>.md` |

---

## Project Structure

```
agent/
├── main.py              # FastAPI app + WebSocket server
├── config.py            # Configuration (loads models.json, providers.json)
├── models.json          # Video/upscale/image model mappings
├── providers.json       # Per-role AI CLI provider/model/effort
├── db/
│   ├── schema.py        # SQLite schema (aiosqlite)
│   └── crud.py          # Async CRUD with column whitelisting
├── models/              # Pydantic models + Literal enums
├── api/                 # REST routes
├── services/
│   ├── flow_client.py   # WS bridge to extension
│   ├── tts.py           # OmniVoice TTS
│   ├── scene_chain.py   # Continuation scene logic
│   ├── cli_providers.py # AI CLI provider config
│   ├── video_reviewer.py# AI vision review
│   └── post_process.py  # ffmpeg trim/merge/music
└── worker/
    └── processor.py     # Queue processor + poller

extension/               # Chrome MV3 extension
skills/                  # AI agent workflow recipes
youtube/
├── auth.py              # OAuth2 multi-channel auth
├── upload.py            # Upload with scheduling
└── channels/            # Per-channel config
    └── <channel_name>/
        ├── client_secrets.json
        ├── token.json
        ├── channel_rules.json
        └── upload_history.json
```

---

## License

MIT — ดัดแปลงจาก [FlowKit](https://github.com/tuannguyenhoangit-droid/google-flow-agent) ของ tuannguyenhoangit-droid
