# emotionGame

A Flask + SocketIO backend for an Unreal Engine emotional intelligence game
where a player helps an NPC who has "lost the ability to name emotions."
The player guesses what emotion the NPC is feeling based on body sensations,
behavioral cues, and conversational context.

## Architecture

```
                     Unreal Engine 5 (C++ client)
                              |
                       SocketIO (ws)
                              |
                  +-----------+-----------+
                  |   camo_server.py      |  Flask entry point (port 5001)
                  |   sockets.py          |  SocketIO event handlers
                  +-----------+-----------+
                              |
        +---------------------+---------------------+
        |                     |                      |
   +----+--------+    +------+------+    +----------+----------+
   |UnrealPhase1 |    | openAI      |    | emotionGameQueries  |
   |(game state  |    | queries.py  |    | (DB: emotion guess) |
   | machine)    |    | (LLM calls) |    +---------------------+
   +----+--------+    +------+------+
        |                     |
   +----+--------+           |            +------------------+
   |emotion_game/|           |            | phase_2_queries  |
   |- npc_intro  |           |            | (storylets,      |
   |- npc_descr  |           |            |  tasks, invent)  |
   |- player_gss |           |            +------------------+
   |- build_*prmpt|          |
   |- get_NPC_mem|           |
   +----+--------+    +------+------+    +------------------+
        |             | OpenAI API  |    | ElevenLabs TTS   |
        |             | (GPT-4o,    |    | API              |
        |             |  GPT-4o-mini|    +--------+---------+
        |             +-------------+             |
   +----+--------+                       +--------+---------+
   |streamNPCresp|                       | tts_cache/       |
   |streamText   |-----------------------+ (cached .mp3)    |
   |(text + TTS) |                       +------------------+
   +-------------+
        |
   +----+--------+            +--------------------------+
   | db.py       |----------->| MySQL (camodb)           |
   | (connection |            | - emotion_guess_game     |
   |  pool, ctx) |            | - npc_user_memory        |
   +-------------+            | - storylets, NPCs, tasks |
                              +--------------------------+
```

## Tech Stack

| Component   | Technology                |
|-------------|---------------------------|
| Backend     | Flask + Flask-SocketIO    |
| LLM         | OpenAI GPT-4o / GPT-4o-mini |
| TTS         | ElevenLabs                |
| Database    | MySQL                     |
| Client      | Unreal Engine 5 (C++)     |
| Audio       | PyAudio + ffmpeg streaming |

## Setup

### 1. Prerequisites

- Python 3.12+
- MySQL 8.0+
- ffmpeg (on PATH)
- Unreal Engine 5 (for client)

### 2. Install

```bash
cd emotionGame-emotion-game-unreal-version
python -m venv egvenv
egvenv\Scripts\activate       # Windows
# source egvenv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 3. Configure

Create a `.env` file:

```
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yourpassword
DB_NAME=camodb
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=sk_...
```

### 4. Database

Import the schema:

```bash
mysql -u root -p < database/camodb_phase1.sql
```

### 5. Run

```bash
python camo_server.py
# Server starts on http://0.0.0.0:5001
```

## API / SocketIO Events

### HTTP Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/tts_audio/<id>` | GET | Serve cached TTS audio file |
| `/match_choice` | POST | Handle storylet choice selection |
| `/update_NPC_user_mem` | POST | Update NPC memory of player |
| `/get_NPC_user_mem` | POST | Retrieve NPC memory of player |

### SocketIO Events (Client -> Server)

| Event | Payload | Description |
|-------|---------|-------------|
| `connect` | -- | Auto-connect, triggers test events |
| `ping` | -- | Health check -> `pong` |
| `register_user` | -- | Join room, start game |
| `player_input` | `{player_text, last_npc_text}` | Player's guess or statement |
| `player_stepped_away` | `{player_text, last_npc_text}` | Player left and returned |
| `get_cur_emotion` | -- | Debug: get current NPC emotion |
| `test_audio` | -- | Debug: test audio channel |

### SocketIO Events (Server -> Client)

| Event | Payload | Description |
|-------|---------|-------------|
| `npc_text_token` | `{token}` | Streaming text token from NPC |
| `npc_audio_chunk` | `{audio_chunk}` | Base64-encoded MP3 chunk |
| `npc_responded` | `{text}` | Full NPC response complete |
| `current_emotion` | string | Current NPC emotion name |
| `correct` | `{num_correct}` | Correct guess count |
| `keepalive` | -- | Connection keepalive |
| `pong` | string | Ping response |
| `test_connect` | `{msg}` | Connection test |

## Game Flow

```
1. Player connects -> register_user -> start_game()
2. NPC introduces self, asks for help
3. Player agrees -> assignEmotion() -> NPC describes feeling
4. Player guesses emotion -> classify_emotion_guess()
   |-- Correct   -> mark_emotion_guessed_correct() -> next emotion
   |-- Incorrect -> NPC gives hints, player tries again
   |-- Other     -> NPC responds naturally (not a guess)
   |-- All done  -> game_over -> NPC thanks player
5. Player can step away and return -> state preserved
```

## Key Files

| File | Purpose |
|------|---------|
| `camo_server.py` | Flask entry point, HTTP routes |
| `sockets.py` | SocketIO event handlers |
| `UnrealPhase1.py` | Game state machine (start/advance/assign) |
| `db.py` | MySQL connection pool + context managers |
| `turnContext.py` | `EmotionGameTurn` dataclass |
| `llm_client.py` | OpenAI client initialization |
| `openAIqueries.py` | LLM: streaming, classification, cue generation |
| `emotionGameQueries.py` | DB: emotion guessing (mark, get, assign) |
| `phase_2_queries.py` | DB: storylets, tasks, inventory, relationships |
| `elevenlabsQueries.py` | ElevenLabs TTS with caching |
| `streamingMP3Player.py` | ffmpeg-based MP3 streaming player |
| `streamNPCresponse/streamTextResponse.py` | Text streaming + TTS audio |
| `voiceRecorder.py` | Microphone recorder (SoundDevice) |
| `emotion_game/` | Game modules: NPC intro, describe, guess, prompts |
| `tests/` | Test suite (31 tests, pytest) |
| `database/camodb_phase1.sql` | Full MySQL schema |
| `emotionGame.py` | CLI/terminal game loop (legacy) |

## Testing

```bash
pytest tests/ -v
# 31 tests: turnContext, openAIqueries, db
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DB_HOST` | MySQL host (default: localhost) |
| `DB_USER` | MySQL user |
| `DB_PASSWORD` | MySQL password |
| `DB_NAME` | MySQL database name |
| `OPENAI_API_KEY` | OpenAI API key |
| `ELEVENLABS_API_KEY` | ElevenLabs API key |
| `FFMPEG_BIN` | Path to ffmpeg (default: ffmpeg) |
