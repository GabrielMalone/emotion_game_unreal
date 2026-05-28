from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import os

# ------------------------------------------------------------------
# Monkey-patch werkzeug to survive WebSocket disconnect during
# streaming.  Without this, a client disconnect while the server is
# mid-emit corrupts the WSGI state and causes a 500 on the *next*
# connection attempt ("write() before start_response").
# See: https://github.com/pallets/werkzeug/issues/2865
# ------------------------------------------------------------------
import werkzeug.serving
_orig_run_wsgi = werkzeug.serving.WSGIRequestHandler.run_wsgi

def _patched_run_wsgi(self):
    # Force werkzeug to re-raise AssertionError instead of generating
    # a 500 error response that corrupts the connection pool.
    self.server.passthrough_errors = True
    try:
        _orig_run_wsgi(self)
    except AssertionError:
        # Client disconnected while we were writing — the pipe is
        # broken.  Swallow silently so the server stays healthy.
        pass

werkzeug.serving.WSGIRequestHandler.run_wsgi = _patched_run_wsgi
# ------------------------------------------------------------------

from sockets import sio, init_socket_events
from phase_2_queries import update_NPC_user_memory_query, get_NPC_user_memory_query

# --------------------------------------------------
load_dotenv()
AUDIO_DIR = "./tts_cache"
os.makedirs(AUDIO_DIR, exist_ok=True)

camo = Flask(__name__)
CORS(camo)
init_socket_events(camo)

# --------------------------------------------------
# UTILITY ROUTES (keep these)
# --------------------------------------------------
@camo.route("/tts_audio/<audio_id>", methods=["GET"])
def tts_audio(audio_id):
    return send_file(f"{AUDIO_DIR}/{audio_id}.mp3", mimetype="audio/mp3")

@camo.route("/update_NPC_user_mem", methods=["POST"])
def update_NPC_user_memory():
    data = request.json
    return update_NPC_user_memory_query(
        idNPC=data["idNPC"],
        idUser=data["idUser"],
        kbText=data["kbText"]
    )

@camo.route("/get_NPC_user_mem", methods=["POST"])
def get_NPC_user_memory():
    data = request.json
    return get_NPC_user_memory_query(
        idUser=data["idUser"],
        idNPC=data["idNPC"]
    )

# --------------------------------------------------
if __name__ == "__main__":
    sio.run(camo, host="0.0.0.0", port=5001, debug=True, use_reloader=False, allow_unsafe_werkzeug=True)
