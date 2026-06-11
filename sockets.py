import logging
import os
import sys

logger = logging.getLogger("sockets")
logger.setLevel(logging.DEBUG)

# Ensure a stderr handler so terminal watchers see socket events.
# Messages also propagate to root → server.log.
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] sockets: %(message)s",
        datefmt="%H:%M:%S",
    ))
    logger.addHandler(sh)

logger.info("=== sockets.py loaded ===")

from flask_socketio import SocketIO, join_room
from UnrealPhase1 import active_turns, start_game, advance_game, currentScene, idUser, idNPC, voiceId
from emotionGameQueries import get_active_emotion, get_num_correct
from db import get_cursor
from input_filter import sanitize_player_input

sio = SocketIO(cors_allowed_origins="*")

# --- audio-streaming gate: block player input while Unreal plays NPC audio ---
_AUDIO_STREAMING = False


def init_socket_events(app):

    sio.init_app(app)

    # --- CATCH-ALL: log every event Unreal sends ---
    @sio.on("*")
    def catch_all(event, data=None):
        logger.info(f"[CATCH-ALL] event='{event}' data={str(data)[:500]}")

    @sio.on("connect")
    def on_connect():
        logger.info("[connect] player connected")
        # Join the room but DON'T start the game yet —
        # wait for register_user from Unreal so the client
        # is fully initialized and ready to receive audio.
        join_room(f"user:{idUser}")
        logger.info(f"[connect] joined room user:{idUser}, waiting for register_user...")

    @sio.on("ping")
    def ping(data=None):
        logger.info(f"[ping] received: {data}")
        sio.emit("pong", "HELLO_FROM_FLASK")

    @sio.on("disconnect")
    def on_disconnect():
        turn = active_turns.get(idUser)
        if turn is not None:
            turn.cancel_stream = True
        logger.info(f"[disconnect] user {idUser} disconnected, cancel_stream set")

    @sio.on("register_user")
    def register_user(data=None):
        player_name = None
        if data and data.get("player_name", "").strip():
            player_name = data["player_name"].strip()
        logger.info(f"[register_user] player_name={player_name}")
        join_room(f"user:{idUser}")
        start_game(sio=sio, player_name=player_name)

    @sio.on("player_input")
    def on_player_input(data):
        logger.info(f"[player_input] data={str(data)[:200]}")
        if not data:
            logger.info("[player_input] empty data, ignoring")
            return
        # --- block input while Unreal is still playing NPC audio ---
        if _AUDIO_STREAMING:
            logger.info("[player_input] ignored — audio still streaming in Unreal")
            return
        turn = active_turns.get(idUser)
        if turn is None:
            logger.info("[player_input] ignored — no active turn for user")
            return
        # Use explicit turn_in_progress flag instead of _lock.locked()
        # to avoid false-positives when lock is held by unrelated code.
        if turn.turn_in_progress:
            logger.info("[player_input] ignored — turn in progress")
            return

        # --- input filtering: non-speech + profanity ---
        raw_text = data.get("player_text", "")
        player_text, was_ignored, had_profanity = sanitize_player_input(raw_text)
        if was_ignored:
            logger.info(f"[player_input] IGNORED non-speech: {raw_text[:100]!r}")
            return
        if had_profanity:
            logger.info(f"[player_input] PROFANITY dropped: {raw_text[:100]!r}")
            return

        # Only cancel if a stream is actually in progress, otherwise
        # we kill _emit_words background tasks from a stream that
        # already finished naturally (breaks lip sync).
        if turn.streaming:
            turn.cancel_stream = True
        advance_game(turn, player_text, data.get("last_npc_text", ""), sio=sio)

    @sio.on("unreal_audio_is_streaming")
    def on_audio_streaming_start(data=None):
        global _AUDIO_STREAMING
        if not _AUDIO_STREAMING:
            _AUDIO_STREAMING = True
            logger.info("[audio_gate] BLOCKED player input")

    @sio.on("unreal_audio_done_streaming")
    def on_audio_streaming_done(data=None):
        global _AUDIO_STREAMING
        if _AUDIO_STREAMING:
            _AUDIO_STREAMING = False
            logger.info("[audio_gate] UNBLOCKED player input")

    @sio.on("npc_audio_ready")
    def on_npc_audio_ready(sid=None):
        logger.info("[npc_audio_ready] Unreal audio reset complete")
        turn = active_turns.get(idUser)
        if turn is None:
            logger.warning("[npc_audio_ready] no active turn — ignoring")
            return
        turn.audio_ready = True

    @sio.on("player_stepped_away")
    def on_player_stepped_away(data=None):
        logger.info(f"[player_stepped_away] data={str(data)[:200]}")
        turn = active_turns.get(idUser)
        if turn is None:
            return
        turn.cancel_stream = True
        if data and data.get("player_text", "").strip():
            raw_text = data.get("player_text", "")
            player_text, was_ignored, had_profanity = sanitize_player_input(raw_text)
            if was_ignored:
                logger.info(f"[player_stepped_away] IGNORED non-speech: {raw_text[:100]!r}")
                return
            if had_profanity:
                logger.info(f"[player_stepped_away] PROFANITY dropped: {raw_text[:100]!r}")
                return
            advance_game(
                turn,
                player_text,
                data.get("last_npc_text", ""),
                sio=sio,
            )

    @sio.on("get_cur_emotion")
    def getCurEmotion(data=None):
        with get_cursor() as (_db, cursor):
            cursor.execute("""
                SELECT e.emotion
                FROM emotion_guess_game g
                JOIN emotion e ON e.idEmotion = g.idEmotion
                WHERE g.idUser = %s
                    AND g.idNPC = %s
                    AND g.active = 1
                LIMIT 1;
            """, (idUser, idNPC))
            row = cursor.fetchone()
        emotion = row[0] if row else "neutral"
        logger.info(f"[get_cur_emotion] emotion={emotion}")
        sio.emit("send_cur_emotion", emotion)
