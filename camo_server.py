import logging
import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# ------------------------------------------------------------------
# Logging setup — all modules use logging.getLogger(__name__)
# ------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG", "") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("camo_server")

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
# Pre-warm: generate emotion cues at startup so the
# first player interaction doesn't pay a blocking
# gpt-4o-mini call (~3-5s) before streaming starts.
# --------------------------------------------------
def _warmup_apis():
    import threading
    def _warm():
        # --- OpenAI: pre-generate emotion cues ---
        try:
            from llm_client import client as openai_client
            import openAIqueries
            openAIqueries.prewarm_cue_cache(openai_client)
        except Exception as e:
            log.warning(f"cue-cache warmup failed (non-fatal): {e}")

        # --- ElevenLabs: fire a real TTS call to warm httpx connection pool ---
        try:
            from elevenlabsQueries import tts
            gen = tts("hello", "XB0fDUnXU5powFXDhCwa", "neutral")
            for _ in gen:  # consume the stream fully
                pass
            log.info("ElevenLabs connection established")
        except Exception as e:
            log.warning(f"ElevenLabs warmup failed (non-fatal): {e}")

    t = threading.Thread(target=_warm, daemon=True)
    t.start()

# --------------------------------------------------
if __name__ == "__main__":
    _warmup_apis()

    # --- Production safety gates ---
    debug_mode = os.getenv("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    unsafe_werkzeug = os.getenv("ALLOW_UNSAFE_WERKZEUG", "").lower() in ("1", "true", "yes")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))

    log.info(f"Starting on {host}:{port}  debug={debug_mode}  allow_unsafe_werkzeug={unsafe_werkzeug}")

    sio.run(
        camo,
        host=host,
        port=port,
        debug=debug_mode,
        use_reloader=False,
        allow_unsafe_werkzeug=unsafe_werkzeug,
    )
