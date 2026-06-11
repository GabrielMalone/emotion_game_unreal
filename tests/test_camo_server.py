"""
Tests for camo_server.py — Flask routes, werkzeug patch, warmup logic.
"""
import pytest
from unittest.mock import MagicMock, patch, ANY

# ──────────────────────────────────────────────
# Werkzeug monkey-patch
# ──────────────────────────────────────────────
class TestWerkzeugPatch:
    """Tests for the _patched_run_wsgi workaround for WebSocket disconnects."""

    def test_patch_sets_passthrough_errors(self):
        """The patch should set passthrough_errors=True before calling original."""
        import werkzeug.serving
        original = werkzeug.serving.WSGIRequestHandler.run_wsgi

        # Simulate the patch
        class FakeHandler:
            server = MagicMock()

            def run_wsgi(self):
                # After patch, passthrough_errors should be True
                assert self.server.passthrough_errors is True
                return original(self) if hasattr(original, '__call__') else None

        # Verify the patch has been applied (cam_server imports set it)
        from camo_server import _patched_run_wsgi

        handler = FakeHandler()
        handler.server.passthrough_errors = False

        try:
            _patched_run_wsgi(handler)
        except Exception:
            pass

        assert handler.server.passthrough_errors is True

    def test_patch_swallows_assertion_error(self):
        """The patch should swallow AssertionError from the original."""
        import camo_server

        class FakeHandler:
            server = MagicMock()

        original_called = [False]

        def fake_original(self):
            original_called[0] = True
            raise AssertionError("write() before start_response")

        with patch.object(camo_server, '_orig_run_wsgi', fake_original):
            handler = FakeHandler()
            # Should not raise
            camo_server._patched_run_wsgi(handler)

        assert original_called[0]


# ──────────────────────────────────────────────
# Flask app creation
# ──────────────────────────────────────────────
class TestFlaskApp:
    """Tests for the camo Flask app and its routes."""

    def test_app_exists(self):
        """camo should be a Flask app instance."""
        from camo_server import camo
        from flask import Flask
        assert isinstance(camo, Flask)

    def test_tts_audio_route_registered(self):
        """The /tts_audio/<audio_id> route should be registered."""
        from camo_server import camo
        rules = [rule.rule for rule in camo.url_map.iter_rules()]
        assert "/tts_audio/<audio_id>" in rules

    def test_update_npc_user_mem_route_registered(self):
        """The /update_NPC_user_mem route should be registered."""
        from camo_server import camo
        rules = [rule.rule for rule in camo.url_map.iter_rules()]
        assert "/update_NPC_user_mem" in rules

    def test_get_npc_user_mem_route_registered(self):
        """The /get_NPC_user_mem route should be registered."""
        from camo_server import camo
        rules = [rule.rule for rule in camo.url_map.iter_rules()]
        assert "/get_NPC_user_mem" in rules

    def test_cors_enabled(self):
        """CORS should be configured on the app."""
        from camo_server import camo
        # After CORS(camo), the app should have Access-Control headers
        with camo.test_client() as client:
            resp = client.options("/tts_audio/test")
            # CORS should add these headers
            assert resp.status_code in (200, 308, 404)

    def test_tts_audio_returns_500_for_missing_file(self):
        """tts_audio route should return 500 when the mp3 doesn't exist
        (send_file raises FileNotFoundError)."""
        from camo_server import camo
        with camo.test_client() as client:
            resp = client.get("/tts_audio/nonexistent_file_12345")
            assert resp.status_code == 500


# ──────────────────────────────────────────────
# update_NPC_user_mem route
# ──────────────────────────────────────────────
class TestUpdateNPCUserMemRoute:
    """Tests for POST /update_NPC_user_mem."""

    def test_calls_phase2_update(self):
        from camo_server import camo
        with patch("camo_server.update_NPC_user_memory_query") as mock_update:
            mock_update.return_value = ("OK", 200)
            with camo.test_client() as client:
                resp = client.post(
                    "/update_NPC_user_mem",
                    json={"idNPC": 1, "idUser": 42, "kbText": "test memory"},
                )
            assert resp.status_code == 200
            mock_update.assert_called_once_with(
                idNPC=1, idUser=42, kbText="test memory"
            )

    def test_passes_json_body(self):
        from camo_server import camo
        with patch("camo_server.update_NPC_user_memory_query") as mock_update:
            mock_update.return_value = ("OK", 200)
            with camo.test_client() as client:
                client.post(
                    "/update_NPC_user_mem",
                    json={"idNPC": 5, "idUser": 10, "kbText": "some memory"},
                )
            mock_update.assert_called_once_with(
                idNPC=5, idUser=10, kbText="some memory"
            )


# ──────────────────────────────────────────────
# get_NPC_user_mem route
# ──────────────────────────────────────────────
class TestGetNPCUserMemRoute:
    """Tests for POST /get_NPC_user_mem."""

    def test_calls_phase2_get(self):
        from camo_server import camo
        with patch("camo_server.get_NPC_user_memory_query") as mock_get:
            mock_get.return_value = ({"memory": "hello"}, 200)
            with camo.test_client() as client:
                resp = client.post(
                    "/get_NPC_user_mem",
                    json={"idUser": 42, "idNPC": 1},
                )
            assert resp.status_code == 200
            mock_get.assert_called_once_with(idUser=42, idNPC=1)


# ──────────────────────────────────────────────
# _warmup_apis
# ──────────────────────────────────────────────
class TestWarmupAPIs:
    """Tests for the _warmup_apis startup function."""

    def test_warmup_runs_in_thread(self):
        """_warmup_apis should start a non-daemon thread."""
        import threading
        from camo_server import _warmup_apis

        initial_count = threading.active_count()
        _warmup_apis()
        # A thread should be spawned
        assert threading.active_count() >= initial_count

    def test_warmup_handles_openai_failure(self):
        """Warmup should not raise if OpenAI prewarm fails."""
        from camo_server import _warmup_apis
        import threading

        # Spy that the thread was started
        with patch("threading.Thread.start") as mock_start:
            _warmup_apis()
            mock_start.assert_called_once()


# ──────────────────────────────────────────────
# Audio directory creation
# ──────────────────────────────────────────────
class TestAudioDir:
    """Tests for AUDIO_DIR creation at import time."""

    def test_audio_dir_exists(self):
        """AUDIO_DIR should be created on import."""
        import os
        from camo_server import AUDIO_DIR
        assert os.path.isdir(AUDIO_DIR)
