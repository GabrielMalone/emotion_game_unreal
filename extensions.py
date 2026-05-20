# extensions.py
import base64
import socketio
import threading
import time
from typing import Callable, Optional


class CamoClientExtension:
    """
    Client-side Socket.IO extension layer.

    Responsibilities:
    - Manage socket connection
    - Register user room
    - Receive NPC text + audio stream
    - Control turn-taking via npc_is_speaking
    - Drive StreamingMP3Player lifecycle
    """

    def __init__(
        self,
        server_url: str,
        idUser: int,
        make_player: Optional[Callable[[], object]] = None,
        post_speech_grace_s: float = 0.35,
        print_text_tokens: bool = True,
    ):
        self.server_url = server_url
        self.idUser = idUser

        self.sio = socketio.Client()

        # ---- turn-taking state
        self.npc_is_speaking = threading.Event()
        self.npc_is_speaking.clear()

        # ---- audio player state
        self._player = None
        self._player_lock = threading.Lock()

        # ---- config
        self._make_player = make_player
        self._post_speech_grace_s = post_speech_grace_s
        self._print_text_tokens = print_text_tokens

        self.last_npc_response: Optional[str] = None
        self.npc_response_ready = threading.Event()
        self.npc_response_ready.clear()

        self._register_handlers()

    # --------------------------------------------------
    # public API
    # --------------------------------------------------
    def connect(self):
        self.sio.connect(self.server_url)

    def disconnect(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass

    def is_npc_speaking(self) -> bool:
        return self.npc_is_speaking.is_set()

    def wait_for_npc(self, timeout: Optional[float] = None) -> bool:
        """
        Block until NPC finishes speaking.
        Returns False if timeout expires.
        """
        start = time.time()
        while self.npc_is_speaking.is_set():
            time.sleep(0.02)
            if timeout is not None and (time.time() - start) > timeout:
                return False
        return True
    
    def wait_for_npc_response(self, timeout: Optional[float] = None) -> bool:
        """
        Block until full NPC response text has been received.
        """
        return self.npc_response_ready.wait(timeout)

    # --------------------------------------------------
    # socket handlers
    # --------------------------------------------------
    def _register_handlers(self):

        @self.sio.event
        def connect():
            print("🔌 Connected to socket server")
            self.sio.emit("register_user", {"idUser": self.idUser})

        # ------------------------------
        # NPC SPEAKING START
        # ------------------------------
        @self.sio.on("npc_speaking")
        def on_npc_speaking(data):
            if not data.get("state"):
                return

            print("🗣️ NPC speaking")
            self.npc_is_speaking.set()

            with self._player_lock:
                if self._make_player:
                    self._player = self._make_player()
                    # StreamingMP3Player supports this
                    if hasattr(self._player, "on_drain"):
                        self._player.on_drain = self._on_audio_drain
                else:
                    self._player = None

        # ------------------------------
        # AUDIO STREAM
        # ------------------------------
        @self.sio.on("npc_audio_chunk")
        def on_audio_chunk(data):
            with self._player_lock:
                if self._player is None:
                    return
                chunk = base64.b64decode(data["audio_b64"])
                self._player.feed(chunk)

        @self.sio.on("npc_audio_done")
        def on_audio_done(_data=None):
            with self._player_lock:
                if self._player is None:
                    return
                print("📦 Server finished sending audio")
                self._player.feed(None)

        # ------------------------------
        # TEXT STREAM
        # ------------------------------
        @self.sio.on("npc_text_token")
        def on_text_token(data):
            if self._print_text_tokens:
                print(data["token"], end="", flush=True)

        @self.sio.on("npc_text_done")
        def on_text_done(data):
            pass

        @self.sio.on("npc_responded")
        def on_npc_responded(data):
            self.last_npc_response = data.get("text", "")
            self.npc_response_ready.set()
        
    # --------------------------------------------------
    # audio drain callback (authoritative turn end)
    # --------------------------------------------------
    def _on_audio_drain(self):
        def delayed_release():
            time.sleep(self._post_speech_grace_s)

            print("🎤 NPC finished speaking (audio drained)")
            self.npc_is_speaking.clear()

            with self._player_lock:
                self._player = None

        threading.Thread(target=delayed_release, daemon=True).start()