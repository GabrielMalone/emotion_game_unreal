"""
Tests for all build_*_prompt.py modules — verify structure, required fields,
and proper prompt construction.
"""
import pytest
from unittest.mock import patch

from turnContext import EmotionGameTurn


# Mock NPC data returned by get_npc() — used by all prompt builders.
MOCK_NPC_DATA = {
    "nameFirst": "Mira",
    "age": 12,
    "gender": "female",
    "role": "A curious forest guide",
    "personality_traits": "warm, kind, playful",
    "emotional_tendencies": "easily moved, wears heart on sleeve",
    "speech_style": "simple, direct, friendly",
    "moral_alignment": "good",
    "BGcontent": "Mira grew up in the enchanted woods helping lost travelers find their way.",
}


def make_turn(**overrides) -> EmotionGameTurn:
    """Create a EmotionGameTurn with sensible defaults + overrides."""
    defaults = {
        "idNPC": 1,
        "idUser": 1,
        "player_name": "Gabriel",
        "current_scene": "Forest clearing at dusk.",
        "voiceId": "test_voice",
        "cur_npc_emotion": "happy",
        "emotion_guessed": "happy",
        "npc_memory": "Gabriel said hello.",
        "player_text": "Are you feeling happy?",
        "last_npc_text": "I feel like my chest is warm.",
        "cues": ["your heart beats faster", "you want to smile", "you feel light"],
        "game_started": True,
        "guessing_started": True,
        "waiting_for_share": False,
        "last_correct_emotion": "",
    }
    defaults.update(overrides)
    turn = EmotionGameTurn(**defaults)
    turn._npc_data = MOCK_NPC_DATA
    return turn


# ─────────────────────────────────────────────────────────────
# build_intro_prompt
# ─────────────────────────────────────────────────────────────
class TestBuildIntroPrompt:
    """Tests for build_intro_prompt()."""

    def test_contains_npc_name(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        prompt = build_intro_prompt(turn)
        assert "Mira" in prompt

    def test_contains_player_name(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn(player_name="Alice")
        prompt = build_intro_prompt(turn)
        assert "Alice" in prompt

    def test_contains_npc_role(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        prompt = build_intro_prompt(turn)
        assert "forest guide" in prompt

    def test_contains_ask_for_help(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        prompt = build_intro_prompt(turn)
        assert "help" in prompt.lower()

    def test_returns_string(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        prompt = build_intro_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


# ─────────────────────────────────────────────────────────────
# build_describe_emotion_prompt
# ─────────────────────────────────────────────────────────────
class TestBuildDescribeEmotionPrompt:
    """Tests for build_describe_emotion_prompt()."""

    def test_contains_npc_persona(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn()
        prompt = build_describe_emotion_prompt(turn)
        assert "Mira" in prompt

    def test_contains_player_name(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn(player_name="Bob")
        prompt = build_describe_emotion_prompt(turn)
        assert "Bob" in prompt

    def test_contains_cue(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn()
        prompt = build_describe_emotion_prompt(turn)
        # At least one of the cues should appear in the prompt
        assert any(cue in prompt for cue in turn.cues)

    def test_returns_string(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn()
        prompt = build_describe_emotion_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_first_turn_includes_thanks_when_not_guessing(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn(guessing_started=False)
        prompt = build_describe_emotion_prompt(turn)
        assert "thank" in prompt.lower()

    def test_next_emotion_mentions_new_feeling(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn(guessing_started=True)
        prompt = build_describe_emotion_prompt(turn)
        assert "new" in prompt.lower()


# ─────────────────────────────────────────────────────────────
# build_correct_guess_prompt
# ─────────────────────────────────────────────────────────────
class TestBuildCorrectGuessPrompt:
    """Tests for build_correct_guess_prompt()."""

    def test_contains_excitement(self):
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn = make_turn(emotion_guessed="happy")
        prompt = build_correct_guess_prompt(turn)
        assert "happy" in prompt

    def test_asks_player_to_share(self):
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn = make_turn()
        prompt = build_correct_guess_prompt(turn)
        assert "share" in prompt.lower() or "ever felt" in prompt.lower()

    def test_returns_string(self):
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn = make_turn()
        prompt = build_correct_guess_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 50


# ─────────────────────────────────────────────────────────────
# build_incorrect_prompt
# ─────────────────────────────────────────────────────────────
class TestBuildIncorrectPrompt:
    """Tests for build_incorrect_prompt()."""

    def test_contains_cues(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn()
        prompt = build_incorrect_prompt(turn)
        assert turn.cues[0] in prompt

    def test_mentions_player_text(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn(player_text="Is it happy?")
        prompt = build_incorrect_prompt(turn)
        assert "Is it happy?" in prompt

    def test_returns_string(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn()
        prompt = build_incorrect_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 100

    def test_fallback_cues_when_none(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn(cues=[])
        prompt = build_incorrect_prompt(turn)
        # Should have injected fallback cues
        assert "flutter" in prompt or "heavy" in prompt or "shiver" in prompt


# ─────────────────────────────────────────────────────────────
# build_disagree_prompt
# ─────────────────────────────────────────────────────────────
class TestBuildDisagreePrompt:
    """Tests for build_disagree_prompt()."""

    def test_contains_player_text(self):
        from emotion_game.build_disagree_prompt import build_disagree_prompt
        turn = make_turn(player_text="I don't want to play")
        prompt = build_disagree_prompt(turn)
        assert "I don't want to play" in prompt

    def test_contains_npc_name(self):
        from emotion_game.build_disagree_prompt import build_disagree_prompt
        turn = make_turn()
        prompt = build_disagree_prompt(turn)
        assert "Mira" in prompt

    def test_returns_string(self):
        from emotion_game.build_disagree_prompt import build_disagree_prompt
        turn = make_turn()
        prompt = build_disagree_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


# ─────────────────────────────────────────────────────────────
# build_share_response_prompt
# ─────────────────────────────────────────────────────────────
class TestBuildShareResponsePrompt:
    """Tests for build_share_response_prompt()."""

    def test_contains_player_text(self):
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        turn = make_turn(player_text="I felt happy when I got a puppy",
                         last_correct_emotion="happy")
        prompt = build_share_response_prompt(turn)
        assert "puppy" in prompt

    def test_contains_last_correct_emotion(self):
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        turn = make_turn(last_correct_emotion="surprised")
        prompt = build_share_response_prompt(turn)
        assert "surprised" in prompt

    def test_returns_string(self):
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        turn = make_turn(last_correct_emotion="happy")
        prompt = build_share_response_prompt(turn)
        assert isinstance(prompt, str)


# ─────────────────────────────────────────────────────────────
# build_no_guess_prompt (did not make guess)
# ─────────────────────────────────────────────────────────────
class TestBuildNoGuessPrompt:
    """Tests for build_no_guess_prompt()."""

    def test_contains_player_text(self):
        from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
        turn = make_turn(player_text="I like this game")
        prompt = build_no_guess_prompt(turn)
        assert "I like this game" in prompt

    def test_contains_cues(self):
        from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
        turn = make_turn()
        prompt = build_no_guess_prompt(turn)
        assert turn.cues[0] in prompt

    def test_returns_string(self):
        from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
        turn = make_turn()
        prompt = build_no_guess_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 100


# ─────────────────────────────────────────────────────────────
# build_end_round_prompt (answered all correctly)
# ─────────────────────────────────────────────────────────────
class TestBuildEndRoundPrompt:
    """Tests for build_end_round_prompt()."""

    def test_contains_player_name(self):
        from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
        turn = make_turn(player_name="Charlie")
        prompt = build_end_round_prompt(turn)
        assert "Charlie" in prompt

    def test_contains_thanks(self):
        from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
        turn = make_turn()
        prompt = build_end_round_prompt(turn)
        assert "thank" in prompt.lower()

    def test_returns_string(self):
        from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
        turn = make_turn()
        prompt = build_end_round_prompt(turn)
        assert isinstance(prompt, str)
        assert len(prompt) > 100
