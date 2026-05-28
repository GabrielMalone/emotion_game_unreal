import sys
import datetime

# ------------------------------------------------------------------
# LOGGING: write all socket events to a file so we can see what
# Unreal is actually sending
# ------------------------------------------------------------------
def _log(msg):
    with open("F:/emotion_game_unreal/socket_debug.log", "a") as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] {msg}\n")
    print(msg)

_log("=== sockets.py loaded ===")

from flask_socketio import SocketIO, join_room
from UnrealPhase1 import active_turns, start_game, advance_game, currentScene, idUser, voiceId
from emotionGameQueries import get_active_emotion, get_num_correct
from db import connect

sio = SocketIO(cors_allowed_origins="*")

def init_socket_events(app):

    sio.init_app(app)

    # --- CATCH-ALL: log every event Unreal sends ---
    @sio.on("*")
    def catch_all(event, data=None):
        _log(f"[CATCH-ALL] event='{event}' data={str(data)[:500]}")

    @sio.on("connect")
    def on_connect():
        _log("[connect] player connected")
        # Join the room but DON'T start the game yet —
        # wait for register_user from Unreal so the client
        # is fully initialized and ready to receive audio.
        join_room(f"user:{idUser}")
        _log(f"[connect] joined room user:{idUser}, waiting for register_user...")

    @sio.on("ping")
    def ping(data=None):
        _log(f"[ping] received: {data}")
        sio.emit("pong", "HELLO_FROM_FLASK")

    @sio.on("disconnect")
    def on_disconnect():
        turn = active_turns.get(idUser)
        if turn is not None:
            turn.cancel_stream = True
        _log(f"[disconnect] user {idUser} disconnected, cancel_stream set")

    @sio.on("register_user")
    def register_user(data=None):
        player_name = None
        if data and data.get("player_name", "").strip():
            player_name = data["player_name"].strip()
        _log(f"[register_user] player_name={player_name}")
        join_room(f"user:{idUser}")
        start_game(sio=sio, player_name=player_name)

    @sio.on("player_input")
    def on_player_input(data):
        _log(f"[player_input] data={str(data)[:200]}")
        if not data:
            _log("[player_input] empty data, ignoring")
            return
        turn = active_turns[idUser]
        # If a turn is already running (lock held), ignore duplicate
        # player_inputs — cancelling mid-stream causes empty responses.
        if turn._lock.locked():
            _log("[player_input] ignored — stream in progress")
            return
        turn.cancel_stream = True
        sio.emit("npc_audio_stop", {}, room=f"user:{turn.idUser}")
        advance_game(turn, data.get("player_text", ""), data.get("last_npc_text", ""), sio=sio)

    @sio.on("npc_audio_ready")
    def on_npc_audio_ready():
        _log("[npc_audio_ready] Unreal audio reset complete")
        turn = active_turns[idUser]
        turn.audio_ready = True

    @sio.on("player_stepped_away")
    def on_player_stepped_away(data=None):
        _log(f"[player_stepped_away] data={str(data)[:200]}")
        turn = active_turns.get(idUser)
        if turn is None:
            return
        turn.cancel_stream = True
        if data and data.get("player_text", "").strip():
            advance_game(
                turn,
                data.get("player_text", ""),
                data.get("last_npc_text", ""),
                sio=sio,
            )

    @sio.on("get_cur_emotion")
    def getCurEmotion(data=None):
        db = connect()
        cursor = db.cursor()
        cursor.execute("""
            SELECT e.emotion
            FROM emotion_guess_game g
            JOIN emotion e ON e.idEmotion = g.idEmotion
            WHERE g.idUser = 1
                AND g.idNPC = 1
                AND g.active = 1
            LIMIT 1;
        """)
        row = cursor.fetchone()
        emotion = row[0] if row else "neutral"
        _log(f"[get_cur_emotion] emotion={emotion}")
        sio.emit("send_cur_emotion", emotion)
