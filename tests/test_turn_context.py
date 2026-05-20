"""
Tests for EmotionGameTurn dataclass and turnContext module.
"""
import pytest
from turnContext import EmotionGameTurn


class TestEmotionGameTurn:
    """Test the EmotionGameTurn dataclass."""

    def test_default_construction(self):
        """Turn should construct with sensible defaults."""
        turn = EmotionGameTurn()
        assert turn.idNPC == 0
        assert turn.idUser == 0
        assert turn.player_name == ""
        assert turn.current_scene == ""
        assert turn.voiceId == ""
        assert turn.cur_npc_emotion == ""
        assert turn.emotion_guessed == ""
        assert turn.emotion_guessed_id == 0
        assert turn.prompt == ""
        assert turn.turn_index == 0
        assert turn.game_started is False
        assert turn.game_over is False
        assert turn.guessing_started is False
        assert turn.npc_memory == ""
        assert turn.player_text == ""
        assert turn.last_npc_text == ""
        assert turn.cues == []

    def test_full_construction(self):
        """Turn should accept all fields."""
        turn = EmotionGameTurn(
            idNPC=1,
            idUser=42,
            player_name="Alice",
            current_scene="Test scene",
            voiceId="abc123",
            cur_npc_emotion="happy",
            emotion_guessed="sad",
            emotion_guessed_id=3,
            prompt="Hello",
            turn_index=5,
            game_started=True,
            game_over=False,
            guessing_started=True,
            npc_memory="some memory",
            player_text="guess",
            last_npc_text="response",
            cues=["cue1", "cue2"],
        )
        assert turn.idNPC == 1
        assert turn.idUser == 42
        assert turn.player_name == "Alice"
        assert turn.current_scene == "Test scene"
        assert turn.voiceId == "abc123"
        assert turn.cur_npc_emotion == "happy"
        assert turn.emotion_guessed == "sad"
        assert turn.emotion_guessed_id == 3
        assert turn.prompt == "Hello"
        assert turn.turn_index == 5
        assert turn.game_started is True
        assert turn.game_over is False
        assert turn.guessing_started is True
        assert turn.npc_memory == "some memory"
        assert turn.player_text == "guess"
        assert turn.last_npc_text == "response"
        assert turn.cues == ["cue1", "cue2"]

    def test_state_transitions_initial(self):
        """New turn should start with game not started, not over."""
        turn = EmotionGameTurn()
        assert turn.game_started is False
        assert turn.game_over is False
        assert turn.guessing_started is False

    def test_state_transitions_started(self):
        """After game starts, guessing should not be started yet."""
        turn = EmotionGameTurn(game_started=True, guessing_started=False)
        assert turn.game_started is True
        assert turn.guessing_started is False

    def test_cues_default_empty_list(self):
        """cues should default to empty list, not shared mutable."""
        t1 = EmotionGameTurn()
        t2 = EmotionGameTurn()
        t1.cues.append("test")
        assert t2.cues == []  # not shared

    def test_repr(self):
        """repr should be informative."""
        turn = EmotionGameTurn(idUser=1, idNPC=2, player_name="Bob")
        r = repr(turn)
        assert "EmotionGameTurn" in r
        assert "Bob" in r
