"""
Tests for emotionGameQueries.py — game state queries and mutations (mocked DB).
"""
import pytest
from unittest.mock import MagicMock, patch

from turnContext import EmotionGameTurn


def make_turn(**overrides) -> EmotionGameTurn:
    defaults = {"idNPC": 1, "idUser": 42, "player_name": "Test"}
    defaults.update(overrides)
    return EmotionGameTurn(**defaults)


class TestMarkEmotionGuessedCorrect:
    """Tests for mark_emotion_guessed_correct()."""

    def test_updates_and_commits(self):
        from emotionGameQueries import mark_emotion_guessed_correct
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            mark_emotion_guessed_correct(make_turn())

        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_passes_correct_ids(self):
        from emotionGameQueries import mark_emotion_guessed_correct
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            mark_emotion_guessed_correct(make_turn(idUser=7, idNPC=3))

        call_args = mock_cursor.execute.call_args
        args, _ = call_args
        assert args[1][0] == 7  # idUser
        assert args[1][1] == 3  # idNPC


class TestGetRemainingEmotions:
    """Tests for get_remaining_emotions()."""

    def test_returns_list_of_strings(self):
        from emotionGameQueries import get_remaining_emotions
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"emotion": "happy"},
            {"emotion": "sad"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_remaining_emotions(make_turn())

        assert result == ["happy", "sad"]

    def test_empty_when_none_remain(self):
        from emotionGameQueries import get_remaining_emotions
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_remaining_emotions(make_turn())

        assert result == []


class TestGetActiveEmotion:
    """Tests for get_active_emotion()."""

    def test_returns_emotion_dict(self):
        from emotionGameQueries import get_active_emotion
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"idEmotion": 1, "emotion": "happy"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_active_emotion(make_turn())

        assert result == {"idEmotion": 1, "emotion": "happy"}

    def test_returns_none_when_no_active(self):
        from emotionGameQueries import get_active_emotion
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_active_emotion(make_turn())

        assert result is None


class TestGetNumCorrect:
    """Tests for get_num_correct()."""

    def test_returns_count(self):
        from emotionGameQueries import get_num_correct
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"num_correct": 3}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_num_correct(make_turn())

        assert result == {"num_correct": 3}


class TestAssignNextEmotion:
    """Tests for assign_next_emotion()."""

    def test_assigns_new_emotion(self):
        from emotionGameQueries import assign_next_emotion
        mock_cursor = MagicMock()
        # First fetchone: deactivate (returns None)
        # Second fetchone: find next unused emotion
        # Only one fetchone() call — after the SELECT query
        mock_cursor.fetchone.side_effect = [{"idEmotion": 2, "emotion": "sad"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        # assign_next_emotion imports transactional from db module at call time
        with patch("db.transactional") as mock_transactional:
            mock_transactional.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = assign_next_emotion(make_turn())

        assert result == {"idEmotion": 2, "emotion": "sad"}
        mock_conn.commit.assert_called()

    def test_returns_none_when_all_completed(self):
        from emotionGameQueries import assign_next_emotion
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [None]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("db.transactional") as mock_transactional:
            mock_transactional.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = assign_next_emotion(make_turn())

        assert result is None

    def test_runs_three_queries_in_transaction(self):
        """Deactivate, find next, insert = 3 execute calls."""
        from emotionGameQueries import assign_next_emotion
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [{"idEmotion": 3, "emotion": "angry"}]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("db.transactional") as mock_transactional:
            mock_transactional.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            assign_next_emotion(make_turn())

        assert mock_cursor.execute.call_count == 3
