"""
Tests for emotion_game build_*_prompt.py — all 8 prompt builders (mocked NPC data).
"""
import pytest
from unittest.mock import patch

from turnContext import EmotionGameTurn

NPC_MOCK = {
    "nameFirst": "Luna",
    "role": "Storyteller",
    "personality_traits": "Warm, curious",
    "speech_style": "Gentle and musical",
    "emotional_tendencies": "Expressive",
    "moral_alignment": "Kind",
    "BGcontent": "Luna lives in a cozy treehouse.",
}


def make_turn(**overrides) -> EmotionGameTurn:
    defaults = {
        "idNPC": 1,
        "idUser": 42,
        "player_name": "Alex",
        "cues": ["flutter in chest", "heavy feeling", "shiver down spine"],
        "npc_memory": "Previous memory text.",
        "player_text": "sad",
        "last_npc_text": "I feel heavy.",
        "emotion_guessed": "sad",
        "last_correct_emotion": "sad",
        "guessing_started": True,
        "game_started": True,
    }
    defaults.update(overrides)
    cues = defaults.pop("cues")
    turn = EmotionGameTurn(**defaults)
    turn.cues = cues
    return turn


# ──────────────────────────────────────────────
# build_intro_prompt
# ──────────────────────────────────────────────
class TestBuildIntroPrompt:
    def test_contains_npc_name_but_not_player_name(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        with patch("emotion_game.build_intro_prompt.get_npc", return_value=NPC_MOCK):
            result = build_intro_prompt(turn)
        assert "Luna" in result
        # Intro prompt asks for the player's name — NPC doesn't know it yet
        assert "Alex" not in result

    def test_mentions_first_meeting(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        with patch("emotion_game.build_intro_prompt.get_npc", return_value=NPC_MOCK):
            result = build_intro_prompt(turn)
        assert "first time" in result.lower() or "first meeting" in result.lower()

    def test_includes_target_audience_section(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        with patch("emotion_game.build_intro_prompt.get_npc", return_value=NPC_MOCK):
            result = build_intro_prompt(turn)
        assert "4-7" in result or "kindergartener" in result

    def test_no_describe_feelings_yet(self):
        from emotion_game.build_intro_prompt import build_intro_prompt
        turn = make_turn()
        with patch("emotion_game.build_intro_prompt.get_npc", return_value=NPC_MOCK):
            result = build_intro_prompt(turn)
        assert "not describe any feelings" in result.lower()


# ──────────────────────────────────────────────
# build_describe_emotion_prompt
# ──────────────────────────────────────────────
class TestBuildDescribeEmotionPrompt:
    def test_contains_npc_and_player(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn()
        with patch("emotion_game.build_describe_emotion_prompt.get_npc", return_value=NPC_MOCK):
            result = build_describe_emotion_prompt(turn)
        assert "Luna" in result
        assert "Alex" in result

    def test_includes_memory_section(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn()
        with patch("emotion_game.build_describe_emotion_prompt.get_npc", return_value=NPC_MOCK):
            result = build_describe_emotion_prompt(turn)
        assert "MEMORY" in result

    def test_first_turn_rules_when_not_guessing_started(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn(guessing_started=False)
        with patch("emotion_game.build_describe_emotion_prompt.get_npc", return_value=NPC_MOCK):
            result = build_describe_emotion_prompt(turn)
        assert "FIRST TURN RULES" in result

    def test_next_emotion_when_guessing_started(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn(guessing_started=True)
        with patch("emotion_game.build_describe_emotion_prompt.get_npc", return_value=NPC_MOCK):
            result = build_describe_emotion_prompt(turn)
        assert "AFTER A CORRECT GUESS" in result

    def test_includes_cues_section(self):
        from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
        turn = make_turn()
        with patch("emotion_game.build_describe_emotion_prompt.get_npc", return_value=NPC_MOCK):
            result = build_describe_emotion_prompt(turn)
        assert "CUES" in result


# ──────────────────────────────────────────────
# build_correct_guess_prompt
# ──────────────────────────────────────────────
class TestBuildCorrectGuessPrompt:
    def test_contains_emotion_word(self):
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn = make_turn(emotion_guessed="sad")
        with patch("emotion_game.build_correct_guess_prompt.get_npc", return_value=NPC_MOCK):
            result = build_correct_guess_prompt(turn)
        assert "sad" in result

    def test_asks_to_share_experience(self):
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn = make_turn(emotion_guessed="happy")
        with patch("emotion_game.build_correct_guess_prompt.get_npc", return_value=NPC_MOCK):
            result = build_correct_guess_prompt(turn)
        assert "share" in result.lower()

    def test_tells_they_got_it_right(self):
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn = make_turn()
        with patch("emotion_game.build_correct_guess_prompt.get_npc", return_value=NPC_MOCK):
            result = build_correct_guess_prompt(turn)
        assert "correctly guessed" in result.lower() or "got it right" in result.lower() or "just correctly" in result.lower()


# ──────────────────────────────────────────────
# build_incorrect_prompt
# ──────────────────────────────────────────────
class TestBuildIncorrectPrompt:
    def test_contains_wrong_guess(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn(player_text="angry", emotion_guessed="angry")
        with patch("emotion_game.build_incorrect_prompt.get_npc", return_value=NPC_MOCK):
            result = build_incorrect_prompt(turn)
        assert "angry" in result

    def test_asks_to_guess_again(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn()
        with patch("emotion_game.build_incorrect_prompt.get_npc", return_value=NPC_MOCK):
            result = build_incorrect_prompt(turn)
        assert "guess" in result.lower()

    def test_includes_three_cues(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn(cues=["a", "b", "c"])
        with patch("emotion_game.build_incorrect_prompt.get_npc", return_value=NPC_MOCK):
            result = build_incorrect_prompt(turn)
        assert "Cue 1" in result and "Cue 2" in result and "Cue 3" in result

    def test_fallback_cues_when_none(self):
        from emotion_game.build_incorrect_prompt import build_incorrect_prompt
        turn = make_turn(cues=[])
        with patch("emotion_game.build_incorrect_prompt.get_npc", return_value=NPC_MOCK):
            result = build_incorrect_prompt(turn)
        assert "flutter" in result.lower() or "heavy" in result.lower()


# ──────────────────────────────────────────────
# build_disagree_prompt
# ──────────────────────────────────────────────
class TestBuildDisagreePrompt:
    def test_contains_player_disagreement(self):
        from emotion_game.build_disagree_prompt import build_disagree_prompt
        turn = make_turn(player_text="no thanks")
        with patch("emotion_game.build_disagree_prompt.get_npc", return_value=NPC_MOCK):
            result = build_disagree_prompt(turn)
        assert "no thanks" in result

    def test_steers_back_to_game(self):
        from emotion_game.build_disagree_prompt import build_disagree_prompt
        turn = make_turn()
        with patch("emotion_game.build_disagree_prompt.get_npc", return_value=NPC_MOCK):
            result = build_disagree_prompt(turn)
        assert "steer" in result.lower() or "game" in result.lower()

    def test_no_greeting(self):
        from emotion_game.build_disagree_prompt import build_disagree_prompt
        turn = make_turn()
        with patch("emotion_game.build_disagree_prompt.get_npc", return_value=NPC_MOCK):
            result = build_disagree_prompt(turn)
        # The rules say "Do NOT quote the child's exact words", so no generic greeting tokens.
        # Check that "hi" or "hello" don't appear as standalone words in the first section.
        first_section = result.split("TARGET AUDIENCE")[0].lower()
        words = first_section.split()
        assert "hi" not in words
        assert "hello" not in words


# ──────────────────────────────────────────────
# build_share_response_prompt
# ──────────────────────────────────────────────
class TestBuildShareResponsePrompt:
    def test_thanks_player_for_sharing(self):
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        turn = make_turn(player_text="I felt sad when my toy broke", last_correct_emotion="sad")
        with patch("emotion_game.build_share_response_prompt.get_npc", return_value=NPC_MOCK):
            result = build_share_response_prompt(turn)
        assert "thank" in result.lower()

    def test_contains_shared_text(self):
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        turn = make_turn(player_text="I felt sad when my toy broke", last_correct_emotion="sad")
        with patch("emotion_game.build_share_response_prompt.get_npc", return_value=NPC_MOCK):
            result = build_share_response_prompt(turn)
        assert "toy broke" in result

    def test_no_new_questions(self):
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        turn = make_turn()
        with patch("emotion_game.build_share_response_prompt.get_npc", return_value=NPC_MOCK):
            result = build_share_response_prompt(turn)
        assert "no new questions" in result.lower() or "not ask any new" in result.lower()


# ──────────────────────────────────────────────
# build_did_not_make_guess_prompt (build_no_guess_prompt)
# ──────────────────────────────────────────────
class TestBuildNoGuessPrompt:
    def test_contains_player_text(self):
        from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
        turn = make_turn(player_text="what is this game?")
        with patch("emotion_game.build_did_not_make_guess_prompt.get_npc", return_value=NPC_MOCK):
            result = build_no_guess_prompt(turn)
        assert "what is this game" in result

    def test_includes_cues(self):
        from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
        turn = make_turn(cues=["cueA", "cueB", "cueC"])
        with patch("emotion_game.build_did_not_make_guess_prompt.get_npc", return_value=NPC_MOCK):
            result = build_no_guess_prompt(turn)
        assert "Cue 1" in result

    def test_asks_to_guess_at_end(self):
        from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
        turn = make_turn()
        with patch("emotion_game.build_did_not_make_guess_prompt.get_npc", return_value=NPC_MOCK):
            result = build_no_guess_prompt(turn)
        assert "guess" in result.lower()


# ──────────────────────────────────────────────
# build_answered_all_correctly_prompt (build_end_round_prompt)
# ──────────────────────────────────────────────
class TestBuildEndRoundPrompt:
    def test_thanks_player_by_name(self):
        from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
        turn = make_turn()
        with patch("emotion_game.build_answered_all_correctly_prompt.get_npc", return_value=NPC_MOCK):
            result = build_end_round_prompt(turn)
        assert "Alex" in result

    def test_no_grades_or_scores(self):
        from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
        turn = make_turn()
        with patch("emotion_game.build_answered_all_correctly_prompt.get_npc", return_value=NPC_MOCK):
            result = build_end_round_prompt(turn)
        # The prompt rules forbid scores/grades — verify the instruction is present
        assert "never give scores or grades" in result.lower()

    def test_mentions_noticing_player_behavior(self):
        from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
        turn = make_turn()
        with patch("emotion_game.build_answered_all_correctly_prompt.get_npc", return_value=NPC_MOCK):
            result = build_end_round_prompt(turn)
        assert "notice" in result.lower()
