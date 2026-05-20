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
        mock_client = MagicMock()
        with patch.object(
            openAIqueries, "generate_emotion_cues", return_value=["a", "b", "c"]
        ):
            cues = openAIqueries.get_cues_for_emotion("happy", mock_client)
            assert cues == ["a", "b", "c"]

    def test_falls_back_on_error(self):
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
