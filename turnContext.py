from dataclasses import dataclass, field
from typing import List
import threading

@dataclass
class EmotionGameTurn:
    idNPC:              int = 0
    idUser:             int = 0
    player_name:        str = ""
    current_scene:      str = ""
    voiceId:            str = ""
    cur_npc_emotion:    str = ""
    emotion_guessed:    str = ""
    emotion_guessed_id: int = 0
    prompt:             str = ""
    turn_index:         int = 0
    game_started:       bool = False
    game_over:          bool = False
    guessing_started:   bool = False
    npc_memory:         str = ""
    player_text:        str = ""
    last_npc_text:      str = ""
    cues:               List[str] = field(default_factory=list)
    cancel_stream:      bool = False
    streaming:          bool = False
    audio_ready:        bool = True   # Unreal sets via npc_audio_ready handshake
    turn_in_progress:   bool = False  # explicit flag — prefer over _lock.locked()
    word_gen:           int = 0       # bumped each stream to cancel old bg tasks
    _lock:              threading.Lock = field(default_factory=threading.Lock)
    _npc_data:          dict | None = None  # cached NPC persona (set once at game start)
