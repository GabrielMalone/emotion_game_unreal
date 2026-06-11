"""
Tests for emotion_game/get_NPC_mem.py — getNPCmem() with mocked DB.
"""
import pytest
from unittest.mock import MagicMock, patch

from turnContext import EmotionGameTurn


def make_turn(**overrides) -> EmotionGameTurn:
    defaults = {"idNPC": 1, "idUser": 42, "player_name": "Test"}
    defaults.update(overrides)
    return EmotionGameTurn(**defaults)


class TestGetNPCMem:
    """Tests for getNPCmem()."""

    def test_returns_memory_text_when_found(self):
        from emotion_game.get_NPC_mem import getNPCmem
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("Player was kind.",)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotion_game.get_NPC_mem.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = getNPCmem(make_turn())

        assert result == "Player was kind."

    def test_returns_empty_string_when_not_found(self):
        from emotion_game.get_NPC_mem import getNPCmem
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotion_game.get_NPC_mem.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = getNPCmem(make_turn())

        assert result == ""

    def test_passes_correct_ids(self):
        from emotion_game.get_NPC_mem import getNPCmem
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("memory",)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotion_game.get_NPC_mem.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            getNPCmem(make_turn(idNPC=5, idUser=99))

        call_args = mock_cursor.execute.call_args
        args, _ = call_args
        assert args[1][0] == 5   # idNPC
        assert args[1][1] == 99  # idUser
