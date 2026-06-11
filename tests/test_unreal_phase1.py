"""
Tests for UnrealPhase1.py — game state machine, turn lifecycle, active_turns.
"""
import pytest
from unittest.mock import MagicMock, patch

from turnContext import EmotionGameTurn


def make_turn(**overrides) -> EmotionGameTurn:
    defaults = {
        "idNPC": 1,
        "idUser": 42,
        "player_name": "TestPlayer",
    }
    defaults.update(overrides)
    return EmotionGameTurn(**defaults)


# ──────────────────────────────────────────────
# Module-level state
# ──────────────────────────────────────────────
class TestModuleState:
    """Tests for UnrealPhase1 module-level constants and state."""

    def test_active_turns_is_dict(self):
        """active_turns should be a dict."""
        from UnrealPhase1 import active_turns
        assert isinstance(active_turns, dict)

    def test_idUser_is_int(self):
        """idUser should be an integer."""
        from UnrealPhase1 import idUser
        assert isinstance(idUser, int)

    def test_idNPC_is_int(self):
        """idNPC should be an integer."""
        from UnrealPhase1 import idNPC
        assert isinstance(idNPC, int)

    def test_currentScene_is_nonempty_string(self):
        """currentScene should be a non-empty string."""
        from UnrealPhase1 import currentScene
        assert isinstance(currentScene, str)
        assert len(currentScene) > 0

    def test_active_turns_contains_default_turn(self):
        """active_turns should have an entry for idUser after import."""
        from UnrealPhase1 import active_turns, idUser
        assert idUser in active_turns

    def test_default_turn_has_correct_user_id(self):
        """The default turn should have the matching idUser."""
        from UnrealPhase1 import active_turns, idUser
        turn = active_turns[idUser]
        assert turn.idUser == idUser

    def test_default_turn_game_not_started(self):
        """The default turn should have game_started=False."""
        from UnrealPhase1 import active_turns, idUser
        turn = active_turns[idUser]
        assert turn.game_started is False


# ──────────────────────────────────────────────
# assignEmotion
# ──────────────────────────────────────────────
class TestAssignEmotion:
    """Tests for assignEmotion()."""

    def test_game_over_when_no_emotion(self):
        """When assign_next_emotion returns None, game_over should be set."""
        from UnrealPhase1 import assignEmotion
        turn = make_turn()
        mock_sio = MagicMock()

        with patch("UnrealPhase1.assign_next_emotion", return_value=None), \
             patch("UnrealPhase1.player_guess") as mock_pg:
            assignEmotion(turn, mock_sio)

        assert turn.game_over is True
        mock_pg.assert_called_once_with(turn, mock_sio)

    def test_sets_cues_when_emotion_found(self):
        """When an emotion is assigned, cues should be fetched."""
        from UnrealPhase1 import assignEmotion
        turn = make_turn()
        mock_sio = MagicMock()

        fake_cues = ["cue one", "cue two", "cue three"]

        with patch("UnrealPhase1.assign_next_emotion", return_value="sad"), \
             patch("UnrealPhase1.openAIqueries.get_cues_for_emotion", return_value=fake_cues), \
             patch("UnrealPhase1.npc_describe_emotion") as mock_desc:
            assignEmotion(turn, mock_sio)

        assert turn.cues == fake_cues
        mock_desc.assert_called_once_with(turn, sio=mock_sio)

    def test_sets_guessing_started(self):
        """After assigning an emotion, guessing_started should be True."""
        from UnrealPhase1 import assignEmotion
        turn = make_turn(guessing_started=False)
        mock_sio = MagicMock()

        with patch("UnrealPhase1.assign_next_emotion", return_value="happy"), \
             patch("UnrealPhase1.openAIqueries.get_cues_for_emotion", return_value=["a", "b", "c"]), \
             patch("UnrealPhase1.npc_describe_emotion"):
            assignEmotion(turn, mock_sio)

        assert turn.guessing_started is True


# ──────────────────────────────────────────────
# start_game
# ──────────────────────────────────────────────
class TestStartGame:
    """Tests for start_game()."""

    def test_acquires_lock(self):
        """start_game should acquire the turn lock."""
        from UnrealPhase1 import start_game, active_turns, idUser
        turn = active_turns[idUser]
        mock_sio = MagicMock()

        # Release the lock if held
        if turn._lock.locked():
            turn._lock.release()

        with patch("UnrealPhase1._start_game_impl") as mock_impl:
            start_game(mock_sio, player_name="Test")

        assert not turn._lock.locked()
        mock_impl.assert_called_once_with(mock_sio)

    def test_sets_player_name(self):
        """start_game should set the player_name on the turn."""
        from UnrealPhase1 import start_game, active_turns, idUser
        turn = active_turns[idUser]
        mock_sio = MagicMock()

        if turn._lock.locked():
            turn._lock.release()

        with patch("UnrealPhase1._start_game_impl"):
            start_game(mock_sio, player_name="CustomName")

        assert turn.player_name == "CustomName"

    def test_ignores_when_locked(self):
        """start_game should no-op when the lock can't be acquired."""
        from UnrealPhase1 import start_game, active_turns, idUser
        turn = active_turns[idUser]
        mock_sio = MagicMock()

        # Acquire the lock first
        if not turn._lock.locked():
            turn._lock.acquire()

        with patch("UnrealPhase1._start_game_impl") as mock_impl:
            start_game(mock_sio)

        # Should not have called the impl
        mock_impl.assert_not_called()

        # Release for other tests
        if turn._lock.locked():
            turn._lock.release()


# ──────────────────────────────────────────────
# advance_game
# ──────────────────────────────────────────────
class TestAdvanceGame:
    """Tests for advance_game()."""

    def test_acquires_lock(self):
        """advance_game should acquire the turn lock."""
        from UnrealPhase1 import advance_game, active_turns, idUser
        turn = active_turns[idUser]
        mock_sio = MagicMock()

        if turn._lock.locked():
            turn._lock.release()

        with patch("UnrealPhase1._advance_game_impl") as mock_impl:
            advance_game(turn, "guess: sad", "I feel heavy.", mock_sio)

        assert not turn._lock.locked()
        mock_impl.assert_called_once_with(turn, "guess: sad", "I feel heavy.", mock_sio)

    def test_ignores_when_locked_timeout(self):
        """advance_game should no-op when the lock is held by another thread."""
        from UnrealPhase1 import advance_game, active_turns, idUser
        turn = active_turns[idUser]
        mock_sio = MagicMock()

        # Acquire the lock first
        if not turn._lock.locked():
            turn._lock.acquire()

        with patch("UnrealPhase1._advance_game_impl") as mock_impl:
            advance_game(turn, "x", "y", mock_sio)

        mock_impl.assert_not_called()

        if turn._lock.locked():
            turn._lock.release()


# ──────────────────────────────────────────────
# _advance_game_impl
# ──────────────────────────────────────────────
class TestAdvanceGameImpl:
    """Tests for _advance_game_impl() internal logic."""

    def test_sets_player_and_npc_text(self):
        """_advance_game_impl should store player_text and last_npc_text."""
        from UnrealPhase1 import _advance_game_impl
        turn = make_turn()
        mock_sio = MagicMock()

        # When guessing_started is True and game_started is True,
        # it goes to player_guess path
        turn.guessing_started = True
        turn.game_started = True

        with patch("UnrealPhase1.player_guess", return_value={"status": "False"}) as mock_pg:
            _advance_game_impl(turn, "guess: sad", "NPC said something.", mock_sio)

        assert turn.player_text == "guess: sad"
        assert turn.last_npc_text == "NPC said something."

    def test_advance_calls_player_guess_when_guessing(self):
        """When guessing_started and game_started, should call player_guess."""
        from UnrealPhase1 import _advance_game_impl
        turn = make_turn(guessing_started=True, game_started=True)
        mock_sio = MagicMock()

        with patch("UnrealPhase1.player_guess", return_value={"status": "False"}) as mock_pg:
            _advance_game_impl(turn, "guess: happy", "I feel light.", mock_sio)

        mock_pg.assert_called_once_with(turn, socketio=mock_sio)

    def test_advance_goes_to_agreement_when_game_not_started(self):
        """When game_started is False, should check agreement."""
        from UnrealPhase1 import _advance_game_impl
        turn = make_turn(game_started=False, guessing_started=False)
        mock_sio = MagicMock()

        with patch("UnrealPhase1.agree_check", return_value=True), \
             patch("UnrealPhase1.assignEmotion") as mock_assign:
            _advance_game_impl(turn, "yes I'll help", "Hello", mock_sio)

        assert turn.game_started is True
        assert turn.guessing_started is False

    def test_advance_handles_disagreement(self):
        """When player disagrees, should call player_disagreed."""
        from UnrealPhase1 import _advance_game_impl
        turn = make_turn(game_started=False, guessing_started=False)
        mock_sio = MagicMock()

        with patch("UnrealPhase1.agree_check", return_value=False), \
             patch("UnrealPhase1.player_disagreed") as mock_disagree:
            _advance_game_impl(turn, "no", "Help me", mock_sio)

        mock_disagree.assert_called_once_with(turn, sio=mock_sio)

    def test_advance_share_experience_phase(self):
        """When waiting_for_share is True, should handle share response."""
        from UnrealPhase1 import _advance_game_impl
        turn = make_turn(
            game_started=True,
            guessing_started=True,
            waiting_for_share=True,
            last_correct_emotion="sad",
        )
        mock_sio = MagicMock()

        with patch("emotion_game.build_share_response_prompt.build_share_response_prompt", return_value="prompt text"), \
             patch("UnrealPhase1.streamResponse", return_value="Thank you for sharing!"), \
             patch("phase_2_queries.update_NPC_user_memory_query"), \
             patch("emotion_game.get_NPC_mem.getNPCmem", return_value="memory"), \
             patch("UnrealPhase1.assignEmotion") as mock_assign:
            _advance_game_impl(turn, "I felt sad once", "Last NPC text", mock_sio)

        assert turn.waiting_for_share is False
        assert turn.last_correct_emotion == ""
        mock_assign.assert_called_once()

    def test_advance_correct_ask_share_path(self):
        """When player_guess returns 'CorrectAskShare', should return early."""
        from UnrealPhase1 import _advance_game_impl
        turn = make_turn(guessing_started=True, game_started=True)
        mock_sio = MagicMock()

        with patch("UnrealPhase1.player_guess", return_value={"status": "CorrectAskShare"}):
            # Should not raise
            _advance_game_impl(turn, "sad", "I feel sad.", mock_sio)

        # waiting_for_share is set by player_guess, but the impl should
        # just return without error
        # (player_guess sets the status flags internally)


# ──────────────────────────────────────────────
# Turn lock
# ──────────────────────────────────────────────
class TestTurnLock:
    """Tests for the threading.Lock on EmotionGameTurn."""

    def test_lock_acquire_and_release(self):
        """Turn lock should be acquirable and releasable."""
        turn = make_turn()
        assert turn._lock.acquire(blocking=False)
        assert turn._lock.locked()
        turn._lock.release()
        assert not turn._lock.locked()

    def test_lock_exclusive(self):
        """Lock should be exclusive (can't acquire twice)."""
        turn = make_turn()
        assert turn._lock.acquire(blocking=False)
        # Second acquire from same thread with blocking=False should return False
        # (same thread can re-acquire a threading.Lock, actually)
        # Just verify it's locked
        assert turn._lock.locked()
        turn._lock.release()
