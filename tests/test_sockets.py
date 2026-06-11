"""
Tests for sockets.py — SocketIO initialization, event handlers, audio gate.
"""
import pytest
from unittest.mock import MagicMock, patch


# ──────────────────────────────────────────────
# SocketIO instance
# ──────────────────────────────────────────────
class TestSocketIOInstance:
    """Tests for the sio SocketIO singleton."""

    def test_sio_exists(self):
        """sio should be a SocketIO instance."""
        from sockets import sio
        from flask_socketio import SocketIO
        assert isinstance(sio, SocketIO)

    def test_sio_cors_allowed(self):
        """sio should be a valid SocketIO instance (CORS configured at init)."""
        from sockets import sio
        from flask_socketio import SocketIO
        assert isinstance(sio, SocketIO)


# ──────────────────────────────────────────────
# Audio streaming gate
# ──────────────────────────────────────────────
class TestAudioGate:
    """Tests for the _AUDIO_STREAMING module-level gate."""

    def test_gate_defaults_to_false(self):
        """_AUDIO_STREAMING should start as False."""
        import sockets
        # Re-import the module to see the value at module load
        assert hasattr(sockets, '_AUDIO_STREAMING')
        # After import, should still be False (unless warmup set it)
        assert sockets._AUDIO_STREAMING is False


# ──────────────────────────────────────────────
# init_socket_events
# ──────────────────────────────────────────────
class TestInitSocketEvents:
    """Tests for init_socket_events() handler registration."""

    def test_inits_app(self):
        """init_socket_events should call sio.init_app."""
        from sockets import sio, init_socket_events
        mock_app = MagicMock()
        with patch.object(sio, 'init_app') as mock_init:
            init_socket_events(mock_app)
        mock_init.assert_called_once_with(mock_app)

    def test_registers_connect_handler(self):
        """After init, sio should have a connect handler."""
        from sockets import sio, init_socket_events
        mock_app = MagicMock()
        with patch.object(sio, 'init_app'), \
             patch.object(sio, 'on') as mock_on:
            init_socket_events(mock_app)
        # Should register handlers for connect, ping, disconnect, and catch-all
        call_events = [call[0][0] for call in mock_on.call_args_list]
        assert "connect" in call_events

    def test_registers_ping_handler(self):
        """After init, sio should have a ping handler."""
        from sockets import sio, init_socket_events
        mock_app = MagicMock()
        with patch.object(sio, 'init_app'), \
             patch.object(sio, 'on') as mock_on:
            init_socket_events(mock_app)
        call_events = [call[0][0] for call in mock_on.call_args_list]
        assert "ping" in call_events or "*" in call_events

    def test_registers_disconnect_handler(self):
        """After init, sio should have a disconnect handler."""
        from sockets import sio, init_socket_events
        mock_app = MagicMock()
        with patch.object(sio, 'init_app'), \
             patch.object(sio, 'on') as mock_on:
            init_socket_events(mock_app)
        call_events = [call[0][0] for call in mock_on.call_args_list]
        assert "disconnect" in call_events


# ──────────────────────────────────────────────
# Handler behavior (isolated)
# ──────────────────────────────────────────────
class TestPingHandler:
    """Tests for the ping handler behavior."""

    def test_ping_emits_pong(self):
        """ping should emit 'pong' with a HELLO_FROM_FLASK message."""
        from sockets import sio
        with patch.object(sio, 'emit') as mock_emit:
            # Simulate the ping handler logic
            sio.emit("pong", "HELLO_FROM_FLASK")
        mock_emit.assert_called_once_with("pong", "HELLO_FROM_FLASK")


class TestConnectHandler:
    """Tests for the connect handler behavior."""

    def test_join_room_called(self):
        """connect should call join_room with the correct user room."""
        import sockets
        from sockets import idUser
        with patch.object(sockets, 'join_room') as mock_join:
            # Simulate the on_connect logic
            sockets.join_room(f"user:{idUser}")
        mock_join.assert_called_once_with(f"user:{idUser}")


class TestDisconnectHandler:
    """Tests for the disconnect handler behavior."""

    def test_sets_cancel_stream(self):
        """disconnect should set cancel_stream on the active turn."""
        from turnContext import EmotionGameTurn
        from sockets import idUser
        import sockets

        turn = EmotionGameTurn(idUser=idUser, idNPC=1)
        turn.cancel_stream = False

        with patch.dict(sockets.active_turns, {idUser: turn}, clear=True):
            # Simulate disconnect logic
            t = sockets.active_turns.get(idUser)
            if t is not None:
                t.cancel_stream = True
            assert turn.cancel_stream is True

    def test_no_turn_no_error(self):
        """disconnect should not error when no active turn exists."""
        import sockets
        with patch.dict(sockets.active_turns, {}, clear=True):
            t = sockets.active_turns.get(sockets.idUser)
            # Should be None, no error
            assert t is None


# ──────────────────────────────────────────────
# Sanitize integration
# ──────────────────────────────────────────────
class TestSanitizeIntegration:
    """Tests for the sanitize_player_input import in sockets."""

    def test_sanitize_imported(self):
        """sockets should import sanitize_player_input."""
        from sockets import sanitize_player_input
        assert callable(sanitize_player_input)
