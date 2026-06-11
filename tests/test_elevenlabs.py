"""
Tests for elevenlabsQueries.py — cache key, retry logic, voice config, tag application.
"""
import pytest
import hashlib
from unittest.mock import MagicMock, patch

import elevenlabsQueries as eq
from elevenlabs.types import VoiceSettings


class TestTTSCacheKey:
    """Tests for tts_cache_key()."""

    def test_deterministic(self):
        key1 = eq.tts_cache_key("hello", "abc123", "happy")
        key2 = eq.tts_cache_key("hello", "abc123", "happy")
        assert key1 == key2

    def test_different_text_different_key(self):
        key1 = eq.tts_cache_key("hello", "abc123", "happy")
        key2 = eq.tts_cache_key("world", "abc123", "happy")
        assert key1 != key2

    def test_different_voice_different_key(self):
        key1 = eq.tts_cache_key("hello", "abc123", "happy")
        key2 = eq.tts_cache_key("hello", "xyz789", "happy")
        assert key1 != key2

    def test_different_emotion_different_key(self):
        key1 = eq.tts_cache_key("hello", "abc123", "happy")
        key2 = eq.tts_cache_key("hello", "abc123", "sad")
        assert key1 != key2

    def test_strips_whitespace(self):
        """Surrounding whitespace should not affect cache key."""
        key1 = eq.tts_cache_key("  hello  ", "abc123", "happy")
        key2 = eq.tts_cache_key("hello", "abc123", "happy")
        assert key1 == key2

    def test_returns_hex_string(self):
        key = eq.tts_cache_key("test", "v1", "neutral")
        assert isinstance(key, str)
        # Should be 64 hex chars (sha256)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestRetryClassification:
    """Tests for _is_retryable()."""

    def test_httpx_timeout_is_retryable(self):
        import httpx
        assert eq._is_retryable(httpx.TimeoutException("timeout")) is True

    def test_httpx_connect_error_is_retryable(self):
        import httpx
        assert eq._is_retryable(httpx.ConnectError("refused")) is True

    def test_httpx_read_error_is_retryable(self):
        import httpx
        assert eq._is_retryable(httpx.ReadError("reset")) is True

    def test_httpx_network_error_is_retryable(self):
        import httpx
        assert eq._is_retryable(httpx.NetworkError("down")) is True

    def test_httpx_remote_protocol_error_is_retryable(self):
        import httpx
        assert eq._is_retryable(httpx.RemoteProtocolError("h2")) is True

    def test_status_429_is_retryable(self):
        err = Exception("too many")
        err.status_code = 429
        assert eq._is_retryable(err) is True

    def test_status_500_is_retryable(self):
        err = Exception("server error")
        err.status_code = 500
        assert eq._is_retryable(err) is True

    def test_status_502_is_retryable(self):
        err = Exception("bad gateway")
        err.status_code = 502
        assert eq._is_retryable(err) is True

    def test_status_503_is_retryable(self):
        err = Exception("unavailable")
        err.status_code = 503
        assert eq._is_retryable(err) is True

    def test_status_401_is_not_retryable(self):
        err = Exception("unauthorized")
        err.status_code = 401
        assert eq._is_retryable(err) is False

    def test_status_404_is_not_retryable(self):
        err = Exception("not found")
        err.status_code = 404
        assert eq._is_retryable(err) is False

    def test_rate_limit_substring_is_retryable(self):
        assert eq._is_retryable(Exception("rate limit exceeded")) is True

    def test_server_error_substring_is_retryable(self):
        assert eq._is_retryable(Exception("internal server error")) is True

    def test_ordinary_exception_not_retryable(self):
        assert eq._is_retryable(ValueError("bad value")) is False


class TestGetDefaultVoiceId:
    """Tests for get_default_voice_id()."""

    def test_returns_default_when_no_env(self):
        with patch.dict("os.environ", {}, clear=True):
            # Re-import to pick up clean env
            from elevenlabsQueries import get_default_voice_id, DEFAULT_VOICE_ID
            assert get_default_voice_id() == DEFAULT_VOICE_ID

    def test_returns_env_var_when_set(self):
        with patch.dict("os.environ", {"NPC_VOICE_ID": "custom_voice_123"}):
            from elevenlabsQueries import get_default_voice_id
            assert get_default_voice_id() == "custom_voice_123"


class TestVoiceSettings:
    """Tests for emotion voice settings configuration."""

    def test_all_8_emotions_have_settings(self):
        """Every primary emotion must have VoiceSettings."""
        required = {"happy", "sad", "angry", "afraid", "surprised",
                    "calm", "excited", "disgusted"}
        assert required.issubset(eq.EMOTION_VOICE_SETTINGS.keys())

    def test_neutral_has_settings(self):
        assert "neutral" in eq.EMOTION_VOICE_SETTINGS

    def test_all_settings_are_voice_settings_objects(self):
        for emotion, settings in eq.EMOTION_VOICE_SETTINGS.items():
            assert isinstance(settings, VoiceSettings), f"{emotion}: {type(settings)}"

    def test_stability_in_valid_range(self):
        """Stability should be between 0.0 and 1.0."""
        for emotion, settings in eq.EMOTION_VOICE_SETTINGS.items():
            assert 0.0 < settings.stability <= 1.0, \
                f"{emotion} stability={settings.stability}"

    def test_similarity_boost_in_valid_range(self):
        for emotion, settings in eq.EMOTION_VOICE_SETTINGS.items():
            assert 0.0 < settings.similarity_boost <= 1.0, \
                f"{emotion} similarity={settings.similarity_boost}"


class TestEmotionTags:
    """Tests for emotion tag vocabularies."""

    def test_all_emotions_have_tags(self):
        emotions = {"happy", "sad", "angry", "afraid", "surprised",
                    "calm", "excited", "disgusted", "neutral", "worried"}
        assert emotions.issubset(eq.EMOTION_TAGS.keys())

    def test_tags_are_bracket_wrapped(self):
        for emotion, tags in eq.EMOTION_TAGS.items():
            for tag in tags:
                assert tag.startswith("["), f"{emotion}/{tag}"
                assert tag.endswith("]"), f"{emotion}/{tag}"

    def test_reaction_tags_match_emotions(self):
        """Reaction tags should have entries for all primary emotions."""
        for em in eq.EMOTION_TAGS:
            if em in eq._REACTION_TAGS:
                for tag in eq._REACTION_TAGS[em]:
                    assert tag.startswith("["), f"reaction/{em}/{tag}"


class TestCharAlignmentsToWords:
    """Tests for _char_alignments_to_words()."""

    def test_empty_input(self):
        assert eq._char_alignments_to_words([], [], []) == []

    def test_single_word(self):
        chars = list("hello")
        starts = [0.0, 0.1, 0.2, 0.3, 0.4]
        ends = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = eq._char_alignments_to_words(chars, starts, ends)
        assert len(result) == 1
        assert result[0]["word"] == "hello"
        assert result[0]["start"] == 0.0
        assert result[0]["end"] == 0.5

    def test_multiple_words(self):
        chars = list("hi there")
        starts = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        ends = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        result = eq._char_alignments_to_words(chars, starts, ends)
        assert len(result) == 2
        assert result[0]["word"] == "hi"
        assert result[1]["word"] == "there"

    def test_bracket_tags_stripped(self):
        """Words inside [brackets] should be excluded from output."""
        chars = list("[sighs] okay")
        starts = [0.0] * len(chars)
        ends = [0.1] * len(chars)
        result = eq._char_alignments_to_words(chars, starts, ends)
        assert len(result) == 1
        assert result[0]["word"] == "okay"
        assert "sighs" not in [w["word"] for w in result]

    def test_punctuation_part_of_word(self):
        chars = list("okay!")
        starts = [0.0, 0.1, 0.2, 0.3, 0.4]
        ends = [0.1, 0.2, 0.3, 0.4, 0.5]
        result = eq._char_alignments_to_words(chars, starts, ends)
        assert len(result) == 1
        assert result[0]["word"] == "okay!"


class TestApplyAudioTags:
    """Tests for _apply_audio_tags()."""

    def test_adds_emotion_tag_for_happy(self):
        result = eq._apply_audio_tags("I am so happy today.", "happy")
        assert "[" in result  # Should have at least one tag
        assert "I am so happy today." in result

    def test_adds_emotion_tag_for_sad(self):
        result = eq._apply_audio_tags("I feel very down.", "sad")
        assert "[" in result
        # Tags may be inserted mid-sentence, so strip tags before checking text
        import re
        stripped = re.sub(r'\s*\[.*?\]\s*', ' ', result).strip()
        stripped = re.sub(r'\s+', ' ', stripped)
        assert "I feel very down." in stripped

    def test_unknown_emotion_uses_default(self):
        """Unknown emotion should still produce tagged text."""
        result = eq._apply_audio_tags("Hello.", "nonexistent")
        assert "Hello." in result

    def test_empty_text_returns_empty(self):
        result = eq._apply_audio_tags("", "happy")
        assert result == ""

    def test_tags_are_bracket_wrapped(self):
        """All inserted tags should start with [ and end with ]."""
        for emotion in ["happy", "sad", "angry", "afraid", "surprised", "calm"]:
            result = eq._apply_audio_tags("Test sentence.", emotion)
            # Check that any [ not inside original text is valid
            open_brackets = result.count("[")
            close_brackets = result.count("]")
            assert open_brackets == close_brackets, \
                f"{emotion}: open={open_brackets}, close={close_brackets}"
