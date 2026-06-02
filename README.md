# emotionGame

A Flask + SocketIO backend for an Unreal Engine 5 emotional intelligence game.
An NPC has lost the ability to name emotions — the player helps by guessing what
they're feeling based on body sensations, behavioral cues, and conversation.

## Architecture

```
                     Unreal Engine 5 (C++ client)
                              │
                       SocketIO (ws)
                              │
                  ┌──────────┴──────────┐
                  │   camo_server.py      │  Flask entry point (port 5001)
                  │   sockets.py          │  SocketIO event handlers
                  └──────────┬──────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                      │
   ┌────┴──────┐    ┌────────┴──────┐    ┌──────────┴──────┐
   │UnrealPhase1 │    │ openAI      │    │ emotionGameQueries  │
   │(game state  │    │ queries.py  │    │ (DB: emotion guess) │
   │ machine)    │    │ (LLM calls) │    └──────────┬──────┘
   └────┬──────┘    └────────┬──────┘               │
        │                    │                ┌─────┴──────┐
   ┌────┴──────┐    ┌────────┴──────┐    ┌────────┴──────┐
   │emotion_game/│    │ OpenAI API  │    │ ElevenLabs TTS │
   │▪ npc_intro  │    │ GPT-4o      │    │ eleven_v3      │
   │▪ npc_descr  │    │ GPT-4o-mini │    │ (Charlotte)    │
   │▪ player_gss │    └─────────────┘    └───────┬──────┘
   │▪ build_*    │                               │
   └────┬──────┘                        ┌────────┴──────┐
        │                                 │ tts_cache/  │
   ┌────┴──────┐                        │ (.mp3 files)│
   │streamNPCres │                        └─────────────┘
   │streamText   │
   │(text + TTS) │
   └────┬──────┘
        │
   ┌────┴──────┐    ┌──────────────────────────────────────┐
   │ db.py       │───▶│ TiDB Cloud (MySQL-compatible, TLS)   │
   │(pool, ctx)  │    │ ▪ emotion_guess_game                 │
   └────────────┘    │ ▪ npc_user_memory                    │
                     │ ▪ emotion, NPCs, storylets, etc      │
                     └──────────────────────────────────────┘
```

## Tech Stack

| Component  | Technology                    |
|------------|-------------------------------|
| Backend    | Flask 3 + Flask-SocketIO 5    |
| LLM        | OpenAI GPT-4o / GPT-4o-mini   |
| TTS        | ElevenLabs eleven_v3          |
| Voice      | Charlotte (`XB0fDUnXU5powFXDhCwa`) |
| Database   | TiDB Cloud Starter (MySQL-compatible, TLS 1.3) |
| Client     | Unreal Engine 5 (C++)         |

## Setup

### 1. Prerequisites

- Python 3.12+
- TiDB Cloud account (free Starter tier — no credit card)
- ffmpeg (on PATH, for local TTS playback)
- Unreal Engine 5 (for client)

### 2. Install

```bash
cd emotion_game_unreal
python -m venv egvenv
source egvenv/bin/activate       # macOS/Linux
# egvenv\Scripts\activate       # Windows
pip install -r requirements.txt
```

### 3. Configure

Create a `.env` file:

```env
# ── Database (TiDB Cloud Starter) ──────────────────────────
DB_HOST=gateway01.us-east-1.prod.aws.tidbcloud.com
DB_USER=youruser.root
DB_PASSWORD=yourpassword
DB_NAME=camodb
DB_PORT=4000
DB_SSL_CA=isrg-root-x1.pem

# ── APIs ───────────────────────────────────────────────────
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=sk_...

# ── Optional overrides ─────────────────────────────────────
NPC_VOICE_ID=XB0fDUnXU5powFXDhCwa    # Charlotte — ElevenLabs voice ID
PLAYER_NAME=Gabriel                    # Default player name
TTS_LOCAL_PLAYBACK=0                   # 1 = play audio locally via ffmpeg
DEBUG_SHORT_RESPONSES=                 # Set to any text to replace ALL NPC output
                                       #   e.g. "Hello." → NPC always says "Hello."
                                       #   Leave empty for normal AI responses
```

> **SSL certificate**: TiDB Cloud Starter uses Let's Encrypt (ISRG Root X1).
> Download the cert from <https://letsencrypt.org/certs/isrgrootx1.pem> and
> place it at the path specified in `DB_SSL_CA`. The connection will fail
> without it — `db.py` enforces `ssl_verify_cert=True` and
> `ssl_verify_identity=True`.

### 4. Database

The database is hosted on **TiDB Cloud** (MySQL-compatible, free Starter tier).
No local MySQL installation is required — just a `mysql` CLI client.

#### 4a. Interactive connection

```bash
mysql -u YOUR_USER -p -h YOUR_HOST -P 4000 \
  --ssl-ca=isrg-root-x1.pem --ssl-mode=VERIFY_IDENTITY \
  camodb
```

Once connected, you can run any ad-hoc SQL:

```sql
SHOW TABLES;
DESCRIBE emotion;
SELECT * FROM emotion LIMIT 5;
```

To create new tables, add columns, or insert data — just run `CREATE TABLE`,
`ALTER TABLE`, `INSERT`, etc. directly in this session. TiDB Cloud Starter is
fully MySQL-compatible.

#### 4b. Apply a SQL file

```bash
# Any .sql file works — new tables, seed data, migrations, etc.
mysql -u YOUR_USER -p -h YOUR_HOST -P 4000 \
  --ssl-ca=isrg-root-x1.pem --ssl-mode=VERIFY_IDENTITY \
  camodb < your_migration.sql
```

#### 4c. Schema reference

The baseline schema is in [`database/camodb_phase1.sql`](database/camodb_phase1.sql).
This file is also used by `start_game.bat` for the initial setup on Windows.

#### 4d. Reset (Windows)

```bash
# Drop + recreate + re-seed the database
start_game.bat
```

Uses the same SSL flags — reads `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`,
`DB_PORT`, and `DB_SSL_CA` from your `.env` file.

### 5. Run

```bash
python camo_server.py
# Server starts on http://0.0.0.0:5001
```

## Game Flow

```
CONNECT ──▶ start_game() auto-fires on connection
  │
  ├─▶ All emotions completed ──▶ game_over ──▶ NPC thanks player
  ├─▶ Active emotion exists   ──▶ resume guessing from where left off
  └─▶ Fresh game ──▶ npc_introduce() ──▶ NPC asks for help
                          │
                    Player responds
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
         AGREES to help          REFUSES
              │                       │
    assignEmotion()             NPC asks again
    (pick next unused                │
     emotion from DB)          tries to convince
              │
    OpenAI generates 3 cues
    (body sensations, behaviors,
     everyday situations)
              │
    npc_describe_emotion()
    (streaming text + TTS audio)
              │
       Player guesses
              │
    ┌─────────┼─────────┐
    ▼         ▼          ▼
 CORRECT  INCORRECT    OTHER
    │         │          │
 mark in   NPC gives   NPC responds
 DB, get   hints,      naturally
 next      try again   (not a guess)
 emotion
    │
    └──▶ repeat until all 8 emotions done ──▶ game_over
```

The player can disconnect and reconnect at any point — state is preserved in
TiDB Cloud and the game resumes transparently.

## SocketIO Events

### Client → Server

| Event | Payload | Description |
|-------|---------|-------------|
| `connect` | — | Auto-joins room, calls `start_game()` |
| `ping` | — | Health check → `pong` |
| `register_user` | `{player_name?}` | Join room, start game with player name |
| `player_input` | `{player_text, last_npc_text}` | Player sends text (guess, answer, or chat) |
| `player_stepped_away` | `{player_text?, last_npc_text?}` | Player left and returned |
| `get_cur_emotion` | — | Debug: query current active emotion |
| `disconnect` | — | Sets `cancel_stream` flag, stops TTS |

### Server → Client

| Event | Payload | Description |
|-------|---------|-------------|
| `register_user` | `{idUser}` | User registered, emitted on connect |
| `game_start` | `{}` | Game started (player agreed or game resumed) |
| `npc_text_token` | `{token}` | Sentence of NPC dialogue (cleaned, no tags) |
| `npc_audio_chunk` | `{audio_chunk}` | Base64-encoded MP3 chunk (32KB) |
| `npc_audio_done` | `{}` | Per-sentence audio finished playing |
| `npc_stream_audio_done` | `{}` | All audio finished — use as "done speaking" signal |
| `show_word` | `{word}` | Single word timed to audio — display each as it arrives |
| `npc_responded` | `{text}` | NPC response complete (non-streaming fallback) |
| `current_emotion` | string | Current NPC emotion name (per-user, during describe) |
| `send_cur_emotion` | string | Current NPC emotion name (broadcast) |
| `correct` | number | Running count of correct guesses |
| `stream_cancelled` | `{}` | Stream aborted (player walked away) |
| `keepalive` | `{}` | Connection keepalive |
| `pong` | `"HELLO_FROM_FLASK"` | Ping response |

## HTTP Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/tts_audio/<audio_id>` | GET | Serve cached TTS .mp3 file |
| `/match_choice` | POST | Handle storylet choice selection (phase 2) |
| `/update_NPC_user_mem` | POST | `{idNPC, idUser, kbText}` — update NPC memory |
| `/get_NPC_user_mem` | POST | `{idNPC, idUser}` — retrieve NPC memory |

## TTS: ElevenLabs v3

### Voice configuration

The default NPC voice is **Charlotte** (`XB0fDUnXU5powFXDhCwa`) — chosen for
natural, emotionally expressive delivery on the eleven_v3 model.

To switch voices, set `NPC_VOICE_ID` in `.env` or change `DEFAULT_VOICE_ID`
in `elevenlabsQueries.py`. A registry of 8 known voices with notes is in
`VOICE_REGISTRY` at the top of that file for quick reference.

> **Important:** Charlotte is the only voice that handles stability as low as
> 0.15 without artifacts. If you switch to Sarah, Amelia, etc., you may need
> to raise the stability floor in `EMOTION_VOICE_SETTINGS`.

### Voice settings per emotion

Stability is tuned into the 0.18–0.35 "creative" range where `[bracket tags]`
have the most impact. Charlotte handles low stability without artifacts.

| Emotion   | Stability | Style | Speed |
|-----------|-----------|-------|-------|
| happy     | 0.22      | 0.55  | 1.10  |
| excited   | 0.18      | 0.60  | 1.20  |
| surprised | 0.15      | 0.65  | 1.20  |
| sad       | 0.20      | 0.50  | 0.75  |
| angry     | 0.18      | 0.60  | 1.20  |
| afraid    | 0.15      | 0.55  | 0.90  |
| disgusted | 0.18      | 0.55  | 0.88  |
| calm      | 0.35      | 0.30  | 0.78  |
| neutral   | 0.35      | 0.32  | 1.00  |
| worried   | 0.25      | 0.48  | 0.95  |

Audio is cached to `tts_cache/` keyed by `sha256(voice_id | emotion | text)`.

### Audio tags

The `_apply_audio_tags()` function wraps NPC dialogue with ElevenLabs v3
`[bracket tags]` for emotional delivery:

- **Emotion direction** — prepended to ~55% of sentences (e.g. `[warmly]`,
  `[sadly]`, `[frustrated]`)
- **Non-verbal reactions** — 20% chance per sentence, post-pended
  (e.g. `[sighs]`, `[laughs]`, `[gulps]`)
- **Pacing/hesitation** — 15% chance, mid-sentence insertion for hesitant
  emotions (e.g. `[hesitates]`, `[stammers]`, `[pause]`)

Tags are stripped from the text sent to Unreal for closed-caption display.

### Error handling & retry

TTS calls are wrapped with automatic retry (`_tts_with_retry` in
`elevenlabsQueries.py`):

- **3 attempts** with exponential backoff: 1s → 2s → 4s (+ random jitter)
- Catches httpx network errors (timeout, connection reset, read errors)
- Catches ElevenLabs API errors (429 rate limit, 5xx server errors)
- Non-retryable errors (4xx auth/bad request) are re-raised immediately
- On retry, the TTS call restarts from scratch — the audio stream is
  idempotent and the cache absorbs any duplicate work

Both `tts()` and `tts_with_timestamps()` inherit retry; their cached
wrappers (`tts_cached`, `tts_with_timestamps_cached`) do too.

## Key Files

| File | Purpose |
|------|---------|
| `camo_server.py` | Flask entry point, HTTP routes, werkzeug WS disconnect patch |
| `sockets.py` | SocketIO event handlers, debug logging, connect/disconnect |
| `UnrealPhase1.py` | Game state machine: `start_game`, `advance_game`, `assignEmotion` |
| `turnContext.py` | `EmotionGameTurn` dataclass (all turn state + threading lock) |
| `db.py` | TiDB Cloud connection pool (5), `get_cursor` and `transactional` context managers, TLS 1.3 with certificate verification |
| `llm_client.py` | OpenAI client init |
| `openAIqueries.py` | LLM: streaming (`GPT-4o`), classification + cue gen (`GPT-4o-mini`) |
| `emotionGameQueries.py` | DB: assign/mark emotions, get active, count correct |
| `phase_2_queries.py` | DB: storylets, storylet choices, tasks, inventory, NPC relationships |
| `elevenlabsQueries.py` | ElevenLabs TTS + caching, per-emotion voice settings, audio tag injection |
| `streamNPCresponse/streamTextResponse.py` | Sentence-by-sentence text + TTS streaming to Unreal |
| `streamingMP3Player.py` | ffmpeg-based local MP3 playback (`TTS_LOCAL_PLAYBACK=1`) |
| `voiceRecorder.py` | Microphone recorder (SoundDevice) |
| `emotion_game/` | 10 modules: NPC intro, describe, guess, 6 prompt builders, NPC memory |
| `tests/` | pytest suite (31 tests: turnContext, openAIqueries, db) |
| `database/camodb_phase1.sql` | Full MySQL-compatible schema + seed data |
| `isrg-root-x1.pem` | ISRG Root X1 certificate for TiDB Cloud TLS connections |
| `start_game.bat` | Windows startup: DB reset + server launch with SSL |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | — | TiDB Cloud hostname |
| `DB_USER` | — | TiDB Cloud user (includes `.root` suffix) |
| `DB_PASSWORD` | — | TiDB Cloud password |
| `DB_NAME` | `camodb` | Database name |
| `DB_PORT` | `4000` | TiDB Cloud port |
| `DB_SSL_CA` | `isrg-root-x1.pem` | Path to ISRG Root X1 certificate |
| `OPENAI_API_KEY` | — | OpenAI API key |
| `ELEVENLABS_API_KEY` | — | ElevenLabs API key |
| `NPC_VOICE_ID` | `XB0fDUnXU5powFXDhCwa` | ElevenLabs voice ID (see `VOICE_REGISTRY` in `elevenlabsQueries.py`) |
| `PLAYER_NAME` | `Gabriel` | Default player name |
| `TTS_LOCAL_PLAYBACK` | `0` | `1` to play audio locally via ffmpeg |

## Testing

```bash
pytest tests/ -v
# 31 tests across turnContext, openAIqueries, and db
```

## Design Decisions

### Auto-start on connect

`sockets.py` calls `start_game()` immediately on `connect` — the player doesn't
need to send `register_user` first. This reduces latency for Unreal clients that
connect at launch and expect the NPC to begin speaking.

### Thread-safe turns

`EmotionGameTurn._lock` is a `threading.Lock` acquired by both `start_game` and
`advance_game`. If a second turn arrives while one is in progress (e.g. player
clicks an emotion during NPC intro), it's silently dropped. Timeout on
`advance_game` is 5 seconds — if the lock isn't released by then, the turn is
skipped.

### Streaming model

Text and audio are streamed sentence-by-sentence (split on `.?!`). Each sentence
triggers:
1. `npc_text_token` — clean text (DO NOT display — arrives BEFORE audio)
2. Multiple `npc_audio_chunk` emits — base64 MP3 in 32KB chunks
3. `npc_audio_done` — per-sentence audio complete
4. Multiple `show_word` emits — `{word}` one word at a time, server-timed to align with audio playback

If the player sends input mid-stream, `cancel_stream` is set and the stream
aborts immediately.

### Word-timed text display (closed captions)

The server emits `show_word` events timed to audio playback. **Unreal must
display text from these events, NOT from `npc_text_token`.** Here's why:

- `npc_text_token` arrives **before** TTS generation — so text appeared
  seconds before audio.
- `show_word` emits `{word}` one word at a time, server-timed using
  ElevenLabs character-level alignment so each word arrives in sync
  with the audio playback.
- Unreal simply appends each arriving word to the display text widget
  — no Tick polling or `GetPlaybackTime()` needed.

Full implementation guide: [`unreal/BLUEPRINT_GUIDE.md`](unreal/BLUEPRINT_GUIDE.md)

C++ component: [`unreal/WordTimingDisplayComponent.h`](unreal/WordTimingDisplayComponent.h) /
[`unreal/WordTimingDisplayComponent.cpp`](unreal/WordTimingDisplayComponent.cpp)

### Werkzeug disconnect patch

Flask's dev server corrupts WSGI state when a client disconnects during
streaming. `camo_server.py` monkey-patches `WSGIRequestHandler.run_wsgi` with
`passthrough_errors=True` to swallow the `AssertionError` instead of returning a
500 that breaks the connection pool.
