"""
Tests for input_filter.py — profanity detection, non-speech detection, sanitization.
All functions are pure — no mocking needed.
"""
import pytest
from input_filter import (
    contains_profanity,
    censor_profanity,
    is_likely_non_speech,
    sanitize_player_input,
)


class TestContainsProfanity:
    """Tests for contains_profanity()."""

    def test_no_profanity_clean_text(self):
        assert contains_profanity("hello there friend") is False

    def test_no_profanity_empty_string(self):
        assert contains_profanity("") is False

    def test_profanity_single_word(self):
        assert contains_profanity("that is shit") is True

    def test_profanity_case_insensitive(self):
        assert contains_profanity("That is SHIT") is True

    def test_profanity_word_boundary(self):
        """'shit' inside another word should NOT match."""
        assert contains_profanity("mishit the ball") is False

    def test_profanity_multiple_words(self):
        assert contains_profanity("fuck shit damn") is True

    def test_profanity_compound(self):
        assert contains_profanity("you motherfucker") is True


class TestCensorProfanity:
    """Tests for censor_profanity()."""

    def test_clean_text_passes_through(self):
        assert censor_profanity("hello there") == "hello there"

    def test_single_profanity_censored(self):
        result = censor_profanity("oh fuck that")
        assert "fuck" not in result
        assert "****" in result

    def test_preserves_word_length(self):
        """Censored word should have same number of asterisks as original letters."""
        result = censor_profanity("you are shit")
        assert "****" in result  # "shit" is 4 letters

    def test_multiple_profanities_censored(self):
        result = censor_profanity("fuck this shit")
        assert "****" in result
        assert result.count("*") == 8  # 4 + 4

    def test_leading_and_trailing_text_preserved(self):
        result = censor_profanity("oh damn it")
        assert result.startswith("oh ")
        assert result.endswith(" it")

    def test_empty_string(self):
        assert censor_profanity("") == ""


class TestIsLikelyNonSpeech:
    """Tests for is_likely_non_speech()."""

    def test_normal_speech(self):
        assert is_likely_non_speech("I feel happy today") is False

    def test_empty_string(self):
        assert is_likely_non_speech("") is True

    def test_whitespace_only(self):
        assert is_likely_non_speech("   \t\n  ") is True

    def test_square_bracket_keyboard(self):
        assert is_likely_non_speech("[keyboard clicking]") is True

    def test_square_bracket_music(self):
        assert is_likely_non_speech("[music playing]") is True

    def test_square_bracket_cough(self):
        assert is_likely_non_speech("[coughing]") is True

    def test_square_bracket_laughter(self):
        assert is_likely_non_speech("[laughter]") is True

    def test_silence_tag(self):
        assert is_likely_non_speech("[silence]") is True

    def test_noise_tag_case_insensitive(self):
        assert is_likely_non_speech("[KEYBOARD TYPING]") is True

    def test_single_letter(self):
        assert is_likely_non_speech("a") is True

    def test_single_letter_with_space(self):
        assert is_likely_non_speech(" a ") is True

    def test_filler_sound_um(self):
        assert is_likely_non_speech("um") is True

    def test_filler_sound_uh(self):
        assert is_likely_non_speech("uh") is True

    def test_punctuation_only(self):
        assert is_likely_non_speech(".,!?") is True

    def test_too_few_letters(self):
        """Words with fewer than 3 letters should be treated as non-speech."""
        assert is_likely_non_speech("hi") is True

    def test_three_letters_is_speech(self):
        assert is_likely_non_speech("yes") is False

    def test_text_with_bracket_in_middle(self):
        """Bracket noise mixed with speech should still be flagged."""
        assert is_likely_non_speech("I think [cough] I am fine") is True

    def test_bare_bracket_noise(self):
        assert is_likely_non_speech("  [background noise]  ") is True

    def test_beep_noise(self):
        assert is_likely_non_speech("[beep]") is True

    def test_engine_noise(self):
        assert is_likely_non_speech("[engine]") is True


class TestSanitizePlayerInput:
    """Tests for sanitize_player_input() — the combined function."""

    def test_clean_input_passes_through(self):
        text, ignored, profanity = sanitize_player_input("hello there")
        assert text == "hello there"
        assert ignored is False
        assert profanity is False

    def test_non_speech_ignored(self):
        text, ignored, profanity = sanitize_player_input("[keyboard clicking]")
        assert text == ""
        assert ignored is True
        assert profanity is False

    def test_profanity_censored_not_ignored(self):
        text, ignored, profanity = sanitize_player_input("you are a bitch")
        assert "bitch" not in text
        assert ignored is False
        assert profanity is True

    def test_empty_string_ignored(self):
        text, ignored, profanity = sanitize_player_input("")
        assert text == ""
        assert ignored is True
        assert profanity is False

    def test_profanity_takes_priority_over_nonspeech(self):
        """A profane short word should be censored, not ignored as non-speech."""
        # "fuck" is 4 letters but is_likely_non_speech checks noise patterns first
        # If it matches a profanity word, it's censored not ignored
        text, ignored, profanity = sanitize_player_input("fuck")
        assert profanity is True
        assert ignored is False

    def test_mixed_noise_and_profanity(self):
        """Non-speech check comes first, so bracket + profanity is ignored."""
        text, ignored, profanity = sanitize_player_input("[cough] fuck")
        assert ignored is True
        assert profanity is False

    def test_short_profanity_word(self):
        """A short (4-letter) profanity should be censored, not ignored."""
        # "fuck" is 4 letters (>= _MIN_LETTERS_FOR_SPEECH=3), is in profanity list
        text, ignored, profanity = sanitize_player_input("fuck")
        assert profanity is True
        assert ignored is False
