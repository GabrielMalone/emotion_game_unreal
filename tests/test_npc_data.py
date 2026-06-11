"""
Tests for emotion_game/npc_data.py — get_npc() with mocked DB cursor.
"""
import pytest
from unittest.mock import MagicMock, patch

MOCK_NPC_ROW = {
    "nameFirst": "Mira",
    "age": 12,
    "gender": "female",
    "role": "A curious forest guide",
    "personality_traits": "warm, kind, playful",
    "emotional_tendencies": "easily moved",
    "speech_style": "simple and friendly",
    "moral_alignment": "good",
    "BGcontent": "Grew up in the enchanted woods.",
}


class TestGetNPC:
    """Tests for get_npc()."""

    def test_returns_npc_data_for_valid_id(self):
        from emotion_game.npc_data import get_npc
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = MOCK_NPC_ROW
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotion_game.npc_data.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_npc(1)

        assert result is not None
        assert result["nameFirst"] == "Mira"
        assert result["role"] is not None

    def test_returns_none_when_not_found(self):
        from emotion_game.npc_data import get_npc
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotion_game.npc_data.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            result = get_npc(999)

        assert result is None

    def test_passes_correct_id_to_query(self):
        from emotion_game.npc_data import get_npc
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = MOCK_NPC_ROW
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("emotion_game.npc_data.get_cursor") as mock_get_cursor:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            get_npc(42)

        # Verify the SQL query was called with the right id
        call_args = mock_cursor.execute.call_args
        assert call_args is not None
        args, _ = call_args
        assert 42 in args[1]  # The second argument is the tuple of params
