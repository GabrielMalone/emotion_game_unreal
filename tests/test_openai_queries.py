"""
Tests for openAIqueries module - JSON parsing, emotion normalization, and cue generation.
"""
import pytest
from unittest.mock import MagicMock, patch
import openAIqueries


class TestParseLLMJson:
    """Tests for parse_llm_json."""

    def test_parse_valid_json(self):
        result = openAIqueries.parse_llm_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_markdown_fence(self):
        result = openAIqueries.parse_llm_json('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_parse_json_with_text_before(self):
        result = openAIqueries.parse_llm_json('Some text {"b": 2} more text')
        assert result == {"b": 2}

    def test_parse_json_with_only_fence(self):
        result = openAIqueries.parse_llm_json('```\n{"c": 3}\n```')
        assert result == {"c": 3}

    def test_parse_empty_string_raises(self):
        with pytest.raises(ValueError, match="Empty LLM response"):
            openAIqueries.parse_llm_json("")

    def test_parse_none_raises(self):
        with pytest.raises(ValueError, match="Empty LLM response"):
            openAIqueries.parse_llm_json(None)

    def test_parse_no_braces_raises(self):
        with pytest.raises(ValueError, match="Could not parse JSON"):
            openAIqueries.parse_llm_json("no json here at all")

    def test_parse_boolean_values(self):
        result = openAIqueries.parse_llm_json('{"agrees_to_help": true}')
        assert result == {"agrees_to_help": True}

    def test_parse_null_values(self):
        result = openAIqueries.parse_llm_json('{"guessed_emotion": null}')
        assert result == {"guessed_emotion": None}


class TestNormalizeEmotion:
    """Tests for normalize_emotion."""

    def test_string_passthrough(self):
        assert openAIqueries.normalize_emotion("happy") == "happy"

    def test_dict_with_emotion_key(self):
        assert openAIqueries.normalize_emotion({"emotion": "sad"}) == "sad"

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            openAIqueries.normalize_emotion(42)

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError):
            openAIqueries.normalize_emotion({})


class TestGenerateEmotionCues:
    """Tests for emotion cue generation (mocked OpenAI)."""

    def test_returns_cues_on_valid_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"cues": ["cue one", "cue two", "cue three"]}'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        cues = openAIqueries.generate_emotion_cues("happy", mock_client)
        assert cues == ["cue one", "cue two", "cue three"]

    def test_handles_markdown_wrapped_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='```json\n{"cues": ["clue A", "clue B", "clue C"]}\n```'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        cues = openAIqueries.generate_emotion_cues("sad", mock_client)
        assert cues == ["clue A", "clue B", "clue C"]

    def test_returns_none_on_malformed_response(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not json at all"))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = openAIqueries.generate_emotion_cues("angry", mock_client)
        assert result is None

    def test_returns_none_on_api_error(self):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API error")

        result = openAIqueries.generate_emotion_cues("calm", mock_client)
        assert result is None


class TestGetCuesForEmotion:
    """Tests for get_cues_for_emotion (the safe wrapper)."""

    def test_returns_generated_cues(self):
        openAIqueries._CUE_CACHE.pop("happy", None)
        mock_client = MagicMock()
        with patch.object(
            openAIqueries, "generate_emotion_cues", return_value=["a", "b", "c"]
        ):
            cues = openAIqueries.get_cues_for_emotion("happy", mock_client)
            assert cues == ["a", "b", "c"]

    def test_falls_back_on_error(self):
        openAIqueries._CUE_CACHE.pop("happy", None)
        mock_client = MagicMock()
        with patch.object(
            openAIqueries,
            "generate_emotion_cues",
            side_effect=Exception("boom"),
        ):
            cues = openAIqueries.get_cues_for_emotion("happy", mock_client)
            assert len(cues) == 3
            assert all(isinstance(c, str) for c in cues)
            assert any("body" in c for c in cues)


class TestClassifyPlayerResponseToGameStart:
    """Tests for classify_player_response_to_game_start()."""

    def test_agreement_returns_true(self):
        from turnContext import EmotionGameTurn
        turn = EmotionGameTurn(player_text="yes", last_npc_text="Will you help?")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"agrees_to_help": true}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = openAIqueries.classify_player_response_to_game_start(turn, mock_client)
        assert result is True

    def test_refusal_returns_false(self):
        from turnContext import EmotionGameTurn
        turn = EmotionGameTurn(player_text="no", last_npc_text="Will you help?")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"agrees_to_help": false}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = openAIqueries.classify_player_response_to_game_start(turn, mock_client)
        assert result is False

    def test_defaults_to_false_on_bad_json(self):
        from turnContext import EmotionGameTurn
        turn = EmotionGameTurn(player_text="maybe", last_npc_text="Will you help?")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="not json"))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        with pytest.raises(ValueError):
            openAIqueries.classify_player_response_to_game_start(turn, mock_client)


class TestClassifyEmotionGuess:
    """Tests for classify_emotion_guess()."""

    def test_returns_guessed_emotion(self):
        from turnContext import EmotionGameTurn
        turn = EmotionGameTurn(player_text="Are you feeling happy?")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"guessed_emotion": "happy"}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = openAIqueries.classify_emotion_guess(turn, mock_client)
        assert result == "happy"

    def test_returns_none_when_not_guessing(self):
        from turnContext import EmotionGameTurn
        turn = EmotionGameTurn(player_text="I like this game")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"guessed_emotion": null}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = openAIqueries.classify_emotion_guess(turn, mock_client)
        assert result is None

    def test_handles_markdown_wrapped_response(self):
        from turnContext import EmotionGameTurn
        turn = EmotionGameTurn(player_text="sad?")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='```json\n{"guessed_emotion": "sad"}\n```'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = openAIqueries.classify_emotion_guess(turn, mock_client)
        assert result == "sad"


class TestPrewarmCueCache:
    """Tests for prewarm_cue_cache()."""

    def test_populates_cache_for_all_eight_emotions(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"cues": ["a", "b", "c"]}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        # Clear cache before test
        openAIqueries._CUE_CACHE.clear()

        openAIqueries.prewarm_cue_cache(mock_client)

        assert len(openAIqueries._CUE_CACHE) == 8
        expected = {"happy", "sad", "angry", "afraid", "surprised",
                    "calm", "excited", "disgusted"}
        assert set(openAIqueries._CUE_CACHE.keys()) == expected

    def test_cache_values_are_lists_of_strings(self):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content='{"cues": ["one", "two", "three"]}'))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        openAIqueries._CUE_CACHE.clear()
        openAIqueries.prewarm_cue_cache(mock_client)

        for emotion, cues in openAIqueries._CUE_CACHE.items():
            assert isinstance(cues, list), f"{emotion}: {type(cues)}"
            assert len(cues) == 3, f"{emotion}: {len(cues)}"
            for cue in cues:
                assert isinstance(cue, str)
