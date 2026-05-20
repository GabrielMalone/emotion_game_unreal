from dataclasses import dataclass, field
from typing import List

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
    cancel_stream:      bool = False  # set by player_stepped_away to halt in-flight OpenAI/TTS stream