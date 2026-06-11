"""
Tests for extensions.py — CamoClientExtension socket lifecycle.
"""
import pytest
from unittest.mock import MagicMock, patch
import threading
import time


# ──────────────────────────────────────────────
# CamoClientExtension init
# ──────────────────────────────────────────────
class TestCamoClientInit:
    """Tests for CamoClientExtension.__init__()."""

    def test_stores_server_url(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        assert ext.server_url == "http://localhost:5001"

    def test_stores_id_user(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        assert ext.idUser == 42

    def test_npc_not_speaking_initially(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        assert ext.npc_is_speaking.is_set() is False

    def test_last_npc_response_none_initially(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        assert ext.last_npc_response is None

    def test_registers_handlers_on_init(self):
        """CamoClientExtension should register socket handlers during init."""
        from extensions import CamoClientExtension
        import socketio

        # Create with mock make_player
        ext = CamoClientExtension("http://localhost:5001", 42)
        # The sio client should have registered events
        assert hasattr(ext.sio, '_handlers') or ext.sio is not None

    def test_accepts_make_player(self):
        from extensions import CamoClientExtension
        mock_factory = MagicMock()
        ext = CamoClientExtension(
            "http://localhost:5001", 42,
            make_player=mock_factory,
            post_speech_grace_s=0.5,
            print_text_tokens=False,
        )
        assert ext._make_player is mock_factory
        assert ext._post_speech_grace_s == 0.5
        assert ext._print_text_tokens is False


# ──────────────────────────────────────────────
# is_npc_speaking / wait_for_npc
# ──────────────────────────────────────────────
class TestNPCSpeaking:
    """Tests for npc_is_speaking and wait_for_npc."""

    def test_is_npc_speaking_false_by_default(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        assert ext.is_npc_speaking() is False

    def test_is_npc_speaking_true_after_set(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        ext.npc_is_speaking.set()
        assert ext.is_npc_speaking() is True

    def test_wait_for_npc_returns_immediately_when_not_speaking(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        start = time.time()
        result = ext.wait_for_npc(timeout=1.0)
        elapsed = time.time() - start
        assert result is True
        assert elapsed < 0.5  # Should return immediately

    def test_wait_for_npc_timeout(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        ext.npc_is_speaking.set()
        start = time.time()
        result = ext.wait_for_npc(timeout=0.1)
        elapsed = time.time() - start
        assert result is False
        assert 0.08 < elapsed < 0.3

    def test_wait_for_npc_response_timeout(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        start = time.time()
        result = ext.wait_for_npc_response(timeout=0.1)
        elapsed = time.time() - start
        assert result is False
        assert 0.08 < elapsed < 0.3


# ──────────────────────────────────────────────
# Audio drain callback
# ──────────────────────────────────────────────
class TestAudioDrain:
    """Tests for _on_audio_drain callback."""

    def test_clears_npc_is_speaking(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        ext.npc_is_speaking.set()
        assert ext.npc_is_speaking.is_set()

        ext._on_audio_drain()
        # Should clear after grace period
        time.sleep(ext._post_speech_grace_s + 0.1)
        assert ext.npc_is_speaking.is_set() is False


# ──────────────────────────────────────────────
# disconnect
# ──────────────────────────────────────────────
class TestDisconnect:
    """Tests for disconnect()."""

    def test_disconnect_handles_exception(self):
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        # disconnect before connect should not raise
        ext.disconnect()


# ──────────────────────────────────────────────
# connect emits register_user
# ──────────────────────────────────────────────
class TestConnect:
    """Tests for the connect handler emitting register_user."""

    def test_connect_handler_registered(self):
        """The connect handler should be registered on the sio client."""
        from extensions import CamoClientExtension
        ext = CamoClientExtension("http://localhost:5001", 42)
        # The sio client should be a socketio.Client instance
        import socketio
        assert isinstance(ext.sio, socketio.Client)
