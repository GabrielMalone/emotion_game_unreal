"""
Tests for phase_2_queries.py — update/get NPC user memory (mocked DB).
"""
import pytest
from unittest.mock import MagicMock, patch


class TestUpdateNPCUserMemory:
    """Tests for update_NPC_user_memory_query()."""

    def test_executes_upsert(self):
        from phase_2_queries import update_NPC_user_memory_query
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ["short memory"]  # below prune threshold
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("phase_2_queries.get_cursor") as mock_get_cursor, \
             patch("phase_2_queries.jsonify") as mock_jsonify:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)
            mock_jsonify.return_value = "OK"

            update_NPC_user_memory_query(1, 42, "Player was nice.")

        # INSERT + SELECT (no UPDATE since memory is short)
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called()

    def test_passes_correct_params(self):
        from phase_2_queries import update_NPC_user_memory_query
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ["short memory"]
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("phase_2_queries.get_cursor") as mock_get_cursor, \
             patch("phase_2_queries.jsonify"):
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            update_NPC_user_memory_query(5, 10, "test memory")

        # First call (INSERT) args
        first_call = mock_cursor.execute.call_args_list[0]
        args = first_call[0]  # positional args tuple
        # Positional params: (query_string, (idNPC, idUser, kbText))
        assert args[1][0] == 5   # idNPC
        assert args[1][1] == 10  # idUser
        assert args[1][2] == "test memory"


class TestGetNPCUserMemory:
    """Tests for get_NPC_user_memory_query()."""

    def test_returns_memory_when_found(self):
        from phase_2_queries import get_NPC_user_memory_query
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"kbText": "some memory", "updatedAt": "2024-01-01"}
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("phase_2_queries.get_cursor") as mock_get_cursor, \
             patch("phase_2_queries.jsonify") as mock_jsonify:
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)
            mock_jsonify.return_value = MagicMock()

            response, status = get_NPC_user_memory_query(42, 1)

        assert status == 200
        mock_jsonify.assert_called_once_with({"memory": {"kbText": "some memory", "updatedAt": "2024-01-01"}})

    def test_passes_correct_params(self):
        from phase_2_queries import get_NPC_user_memory_query
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        with patch("phase_2_queries.get_cursor") as mock_get_cursor, \
             patch("phase_2_queries.jsonify"):
            mock_get_cursor.return_value.__enter__.return_value = (mock_conn, mock_cursor)

            get_NPC_user_memory_query(7, 3)

        call_args = mock_cursor.execute.call_args
        args, _ = call_args
        assert args[1][0] == 3  # idNPC (first positional in query is idNPC)
        assert args[1][1] == 7  # idUser
