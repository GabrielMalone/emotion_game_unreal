from dataclasses import dataclass, field
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
    cues:               list[str] = field(default_factory=list)
    cancel_stream:      bool = False
    streaming:          bool = False
    audio_ready:        bool = True   # Unreal sets via npc_audio_ready handshake
    turn_in_progress:     bool = False  # explicit flag — prefer over _lock.locked()
    waiting_for_name:     bool = False  # NPC asked for player's name, awaiting response
    waiting_for_share:    bool = False  # player must share an experience before next emotion
    waiting_for_continue: bool = False  # game paused after share, waiting for Unreal 'game_continue'
    name_ask_from_continue: bool = False  # name-ask triggered by continue_game (skip intro)
    last_correct_emotion: str  = ""     # emotion word the player just guessed correctly
    word_gen:             int  = 0      # bumped each stream to cancel old bg tasks
    _word_done_event:     threading.Event = field(default_factory=threading.Event)
    _lock:                threading.Lock = field(default_factory=threading.Lock)
    _npc_data:            dict | None = None  # cached NPC persona (set once at game start)
