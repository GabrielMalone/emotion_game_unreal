# emotionGame — Architecture Overview

> **Updated**: 2025-07-15  
> **Purpose**: Quick mental model for anyone working on this codebase (including future you).

---

## What does this project do?

A Flask + SocketIO backend for an Unreal Engine 5 emotional intelligence game.
An NPC has lost the ability to name emotions — the player helps by guessing what
the NPC is feeling based on body sensations, behavioral cues, and conversation.
8 emotions, streaming GPT-4o dialogue + ElevenLabs text-to-speech with word-level
lip-sync timing.

---

## Project map (every file, what it does)

### Entry points

| File | Role |
|---|---|
| `camo_server.py` | Flask app. Mounts SocketIO, defines HTTP routes, pre-warms APIs, calls `sio.run()`. |
| `start_game.sh` / `start_game.bat` | Launch scripts: parse `.env`, reset DB (`camodb_phase1.sql`), prompt for player name, start server. |
| `requirements.txt` | Dependencies: flask, flask-socketio, openai, elevenlabs, mysql-connector-python, etc. |

### Core server layer

| File | Role |
|---|---|
| `sockets.py` | All SocketIO event handlers. `connect`, `register_user`, `player_input`, `player_stepped_away`, `get_cur_emotion`, audio gate events (`unreal_audio_is_streaming` / `unreal_audio_done_streaming`). All events logged to `socket_debug.log`. Calls `UnrealPhase1.start_game` / `advance_game`. |
| `UnrealPhase1.py` | **Game state machine**. Singleton `turn` object. Functions: `start_game()`, `advance_game()`, `assignEmotion()`. Game phases: intro → agree_check → assign_emotion → describe → guess → (correct/incorrect) → repeat. |
| `turnContext.py` | `EmotionGameTurn` dataclass — holds all per-turn state: `idNPC`, `idUser`, `player_name`, `current_scene`, `voiceId`, `cur_npc_emotion`, `emotion_guessed`, `prompt`, `turn_index`, `game_started`, `game_over`, `guessing_started`, `npc_memory`, `player_text`, `last_npc_text`, `cues`, `cancel_stream`, `streaming`, `audio_ready`, `turn_in_progress`, `word_gen`, `_lock`. |
| `input_filter.py` | Sanitizes speech-to-text input from Unreal. Filters: (1) non-speech artifacts (`[keyboard clicking]`, `[music]`, filler sounds), (2) profanity (censors with asterisks). Returns `(cleaned_text, was_ignored, had_profanity)`. |

### LLM layer (OpenAI)

| File | Role |
|---|---|
| `llm_client.py` | Creates `OpenAI` client from env var `OPENAI_API_KEY`. |
| `openAIqueries.py` | All GPT calls: `getResponseStream()` (GPT-4o streaming), `classify_player_response_to_game_start()` (yes/no agreement), `classify_emotion_guess()` (maps text→emotion), `generate_emotion_cues()` (GPT-4o-mini, 3 body-sensation clues), `get_cues_for_emotion()` (with pre-warmed cache), `prewarm_cue_cache()` (generates all 8 at startup). Also `parse_llm_json()` — robust JSON extraction from LLM output. |

### TTS layer (ElevenLabs)

| File | Role |
|---|---|
| `elevenlabsQueries.py` | **~300 lines**. Voice config (`DEFAULT_VOICE_ID`, `VOICE_REGISTRY`), per-emotion `VoiceSettings` (stability 0.15–0.35), `EMOTION_TAGS`/`_REACTION_TAGS`/`_PACING_TAGS` for v3 bracket-tag delivery, `_apply_audio_tags()`, `tts()` (with retry), `tts_with_timestamps()` (character alignment for lip sync), `tts_cached()` (sha256 in `tts_cache/`), `saveAudio()`, `_tts_with_retry()` (exponential backoff + jitter). |
| `design_voice.py` | One-shot script: design custom ElevenLabs voice via Voice Design v3. Generates 3 previews, saves mp3s to `voice_previews/`, lets you pick one. |

### Database layer (TiDB Cloud MySQL)

| File | Role |
|---|---|
| `db.py` | MySQL connection pool (`MySQLConnectionPool`, pool_size=5). Context managers: `get_cursor()` (auto-close), `transactional()` (commit/rollback). Reads `.env` for credentials + SSL (`isrg-root-x1.pem`). |
| `emotionGameQueries.py` | Game-specific DB queries: `mark_emotion_guessed_correct()`, `get_remaining_emotions()`, `get_active_emotion()`, `get_num_correct()`, `assign_next_emotion()`. |
| `phase_2_queries.py` | `update_NPC_user_memory_query()` and `get_NPC_user_memory_query()` — NPC knowledge base persistence. |
| `database/camodb_phase1.sql` | Full schema: NPC, user, storylet, emotion, emotion_guess_game, npc_user_memory, tasks, items, relationships, etc. |

### Streaming pipeline

| File | Role |
|---|---|
| `streamNPCresponse/streamTextResponse.py` | **The heart of NPC output**. `streamResponse()`: streams GPT-4o tokens → accumulates sentences → per sentence: strips `[tags]`, emits `npc_text_token`, calls `tts_with_timestamps_cached()`, emits `npc_audio_chunk` (base64, 32KB), spawns background task `_emit_words()` that fires `show_word` events timed to ElevenLabs character alignment. Handles `cancel_stream`, `word_gen` bump for cancellation. `DEBUG_SHORT_RESPONSES` env var short-circuits for testing. |

### Game logic modules (`emotion_game/`)

| File | Role |
|---|---|
| `emotion_game/npc_introduce.py` | `npc_introduce()`: NPC greets player, asks for help. `agree_check()`: calls GPT-4o-mini to classify yes/no. `player_disagreed()`: NPC tries to convince. |
| `emotion_game/npc_describe_emotion.py` | `npc_describe_emotion()`: NPC describes feelings using 3 pre-generated cues. Streams response. |
| `emotion_game/player_guess.py` | `player_guess()`: classifies player's emotion guess (GPT-4o-mini), branches: correct (mark DB, next emotion), incorrect (NPC gives hints), other (natural response), game over. |
| `emotion_game/build_*.py` | Prompt builders: `build_intro_prompt.py`, `build_describe_emotion_prompt.py`, `build_incorrect_prompt.py`, `build_no_guess_prompt.py` (`build_did_not_make_guess_prompt.py`), `build_disagree_prompt.py`, `build_answered_all_correctly_prompt.py`. |
| `emotion_game/get_NPC_mem.py` | `getNPCmem()`: retrieves NPC's memory of this player. |
| `emotion_game/npc_data.py` | NPC data constants. |

### Unreal Engine integration

| File | Role |
|---|---|
| `extensions.py` | `CamoClientExtension` — client-side SocketIO wrapper for Python testing (not Unreal). Manages connect, audio player lifecycle, `npc_is_speaking` event, `wait_for_npc()`. |
| `unreal/BLUEPRINT_GUIDE.md` | How to wire Unreal Blueprints for word-timed text display using `show_word` events. |
| `unreal/WordTimingDisplayComponent.h/.cpp` | C++ component for Unreal: accumulates words from `show_word`, clears on `npc_audio_done`/`npc_audio_stop`. |

---

## SocketIO event flow

### Client → Server

| Event | When | Payload |
|---|---|---|
| `connect` | Client connects | — |
| `register_user` | Unreal ready to receive | `{player_name?}` |
| `player_input` | Player speaks (via STT) | `{player_text, last_npc_text}` |
| `player_stepped_away` | Player left and returned | `{player_text?, last_npc_text?}` |
| `get_cur_emotion` | Debug: query active emotion | — |
| `unreal_audio_is_streaming` | Unreal starts playing audio | — |
| `unreal_audio_done_streaming` | Unreal finished playing audio | — |
| `npc_audio_ready` | Unreal audio reset complete | — |
| `disconnect` | Client disconnects | — |

### Server → Client

| Event | When | Payload |
|---|---|---|
| `game_start` | Game begins/resumes | `{}` |
| `remaining_emotions` | Game starts | `{remaining_emotions: [...]}` |
| `npc_text_token` | Each sentence (pre-audio) | `{token: "..."}` |
| `npc_audio_chunk` | Per 32KB audio fragment | `{audio_chunk: "<base64>"}` |
| `npc_audio_done` | Per-sentence audio finished | `{}` |
| `npc_stream_audio_done` | All audio finished | `{}` |
| `show_word` | Each word, timed to audio | `{word: "..."}` |
| `npc_responded` | Full NPC response text | `{text: "..."}` |
| `send_cur_emotion` | Current NPC emotion | string |
| `correct` | Running correct count | number |
| `stream_cancelled` | Stream aborted | `{}` |
| `keepalive` | Heartbeat during streaming | `{}` |

### Turn-taking gates

Two layers prevent overlapping input:

1. **`_AUDIO_STREAMING`** (sockets.py): global flag. Unreal sets via `unreal_audio_is_streaming` / `unreal_audio_done_streaming`. Blocks `player_input` while Unreal is still playing audio.

2. **`turn.turn_in_progress`** (UnrealPhase1.py): per-turn flag + `_lock`. Prevents emotion clicks or new input from sneaking in during an active turn.

---

## Database tables (key ones for Phase 1)

| Table | Purpose |
|---|---|
| `emotion` | Lookup: 8 emotion names (`happy`, `sad`, `angry`, `afraid`, `surprised`, `calm`, `excited`, `disgusted`) |
| `emotion_guess_game` | Per-user, per-NPC, per-emotion tracking: `active`, `described`, `guessed_correctly`, `completedAt` |
| `npc_user_memory` | NPC's knowledge base about a player (`kbText` LONGTEXT, append-only with timestamps) |
| `NPC`, `user`, `storylet`, `tasks`, `playerNPCrelationship`, etc. | Phase 2+ content |

---

## Environment variables (`.env`)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `OPENAI_API_KEY` | Yes | — | GPT-4o / GPT-4o-mini |
| `ELEVENLABS_API_KEY` | Yes | — | TTS |
| `DB_HOST` | Yes | — | TiDB Cloud host |
| `DB_USER` | Yes | — | TiDB user |
| `DB_PASSWORD` | Yes | — | TiDB password |
| `DB_NAME` | Yes | `camodb` | Database name |
| `DB_PORT` | — | `4000` | TiDB port |
| `DB_SSL_CA` | Yes | `isrg-root-x1.pem` | TLS cert |
| `PLAYER_NAME` | — | `Gabriel` | Default player name |
| `NPC_VOICE_ID` | — | code default | Override voice |
| `DEBUG_SHORT_RESPONSES` | — | — | Replace all NPC output with fixed text |
| `DB_DEBUG_PASSWORD` | — | — | Local MySQL password (debug mode) |
| `SOCKET_DEBUG_LOG` | — | `socket_debug.log` | Socket event log path |
| `FLASK_DEBUG` | — | — | Enable Flask debug mode |
| `HOST` | — | `0.0.0.0` | Bind address |
| `PORT` | — | `5001` | Bind port |

---

## Game state machine (UnrealPhase1.py)

```
CONNECT → register_user → start_game()
  ├─ All 8 emotions guessed → game_over → NPC thanks player
  ├─ Active emotion exists → resume guessing
  └─ Fresh game → npc_introduce() → NPC asks for help
                    │
              Player responds
                    │
            ┌───────┴───────┐
            ▼               ▼
       AGREES            REFUSES
            │               │
      game_start      NPC tries again
            │
      assign_next_emotion() (DB)
            │
      generate 3 cues (OpenAI, cached)
            │
      npc_describe_emotion() (streaming)
            │
        Player guesses
            │
      ┌─────┼─────┐
      ▼     ▼     ▼
   CORRECT INCORRECT OTHER
      │     │     │
   mark DB hints  natural response
   next    try    (not a guess)
   emotion again
      │
      └──→ repeat until all 8 done → game_over
```

---

## Key design decisions

1. **Audio-first turn gating**: Unreal controls when player input is allowed via `unreal_audio_is_streaming` / `unreal_audio_done_streaming`. The server never assumes the client is ready.

2. **Word-level lip sync**: ElevenLabs character alignment → server calculates timing → `show_word` events fire at the right moment via `sio.start_background_task()`. No `GetPlaybackTime()` needed on Unreal side.

3. **Cue pre-warming**: `prewarm_cue_cache()` generates all 8 emotion cues at startup (GPT-4o-mini) so the first turn doesn't have a 3–5s cold-start delay. Fallback cues if generation fails.

4. **TTS caching**: `tts_cache/` stores mp3s keyed by `sha256(voice_id | emotion | text)`. Same text+emotion → instant cache hit.

5. **TTS retry with backoff**: Network hiccups, 429s, and 5xx from ElevenLabs are retried 3x with exponential backoff + jitter.

6. **Input sanitization**: All player text from Unreal STT passes through `input_filter.py` — non-speech artifacts are dropped, profanity is censored.

7. **Player name flow**: `start_game.sh` prompts → `PLAYER_NAME` env var → `UnrealPhase1.start_game()` default. Unreal can override via `register_user({player_name: ...})`.

8. **Debug mode**: Set `DEBUG_SHORT_RESPONSES=Hello.` in `.env` → all NPC output replaced with that text. Also switches DB to localhost.

---

## Running

```bash
# Full startup (DB reset + name prompt + server)
./start_game.sh

# Or directly
python camo_server.py

# Design a new voice
python design_voice.py
```

Server runs on `http://0.0.0.0:5001`.
