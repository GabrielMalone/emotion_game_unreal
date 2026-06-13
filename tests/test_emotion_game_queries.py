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


# ------------------------------------------------------------------
# New: guess attempt logging + share story persistence
# ------------------------------------------------------------------

class TestLogGuessAttempt:
    """Tests for log_guess_attempt()."""

    def test_inserts_correct_guess(self):
        from emotionGameQueries import log_guess_attempt
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 42
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        turn = make_turn(player_name="Alice", emotion_guessed_id=3)
        turn.idUser = 1
        turn.idNPC = 2

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = log_guess_attempt(turn, player_guess="happy", correct=True,
                                       feedback_text="Yes! That's right!")

        assert result == 42
        mock_conn.commit.assert_called_once()
        call_args = mock_cursor.execute.call_args
        args, _ = call_args
        params = args[1]  # positional params tuple
        assert params[0] == 1   # idUser
        assert params[1] == 2   # idNPC
        assert params[2] == 3   # idEmotion
        assert params[3] == "happy"  # player_guess
        assert params[4] == 1   # correct
        assert params[5] == "Alice"  # player_name
        assert "Yes!" in params[6]   # feedback_text

    def test_inserts_incorrect_guess_with_active_emotion(self):
        from emotionGameQueries import log_guess_attempt
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 7
        mock_cursor.fetchone.return_value = {"idEmotion": 4, "emotion": "sad"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        turn = make_turn(player_name="Bob")

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = log_guess_attempt(turn, player_guess="angry", correct=False)

        assert result == 7
        # For incorrect guesses, get_active_emotion is called (a second
        # get_cursor context) — that means execute is called at least twice
        # (once for the active query, once for the insert)
        assert mock_cursor.execute.call_count >= 2

    def test_returns_none_when_no_emotion(self):
        from emotionGameQueries import log_guess_attempt
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # no active emotion
        mock_cursor.lastrowid = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        turn = make_turn()  # no emotion_guessed_id

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = log_guess_attempt(turn, player_guess="hello", correct=False)

        assert result is None
        mock_conn.commit.assert_not_called()


class TestUpdateShareStory:
    """Tests for update_share_story()."""

    def test_updates_latest_attempt(self):
        from emotionGameQueries import update_share_story
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        turn = make_turn(idUser=5, idNPC=3)

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = update_share_story(turn, share_story="I felt happy when...")

        assert result is True
        mock_conn.commit.assert_called_once()

    def test_skips_empty_story(self):
        from emotionGameQueries import update_share_story
        mock_cursor = MagicMock()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        turn = make_turn()

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = update_share_story(turn, share_story="   ")

        assert result is False
        mock_conn.commit.assert_not_called()


class TestGetPlayerGameLog:
    """Tests for get_player_game_log()."""

    def test_returns_chronological_log(self):
        from emotionGameQueries import get_player_game_log
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            {"idAttempt": 1, "player_name": "Alice", "emotion": "happy",
             "player_guess": "happy", "correct": 1,
             "feedback_text": "Yes!", "share_story": "I was happy when...",
             "attemptedAt": "2026-01-01 12:00:00"},
            {"idAttempt": 2, "player_name": "Alice", "emotion": "sad",
             "player_guess": "angry", "correct": 0,
             "feedback_text": "Not quite...", "share_story": None,
             "attemptedAt": "2026-01-01 12:01:00"},
        ]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotionGameQueries.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_player_game_log(id_user=1, id_npc=2)

        assert len(result) == 2
        assert result[0]["emotion"] == "happy"
        assert result[0]["share_story"] is not None
        assert result[1]["correct"] == 0
