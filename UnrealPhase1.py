import logging
from emotion_game.npc_introduce import npc_introduce, agree_check, player_disagreed
from emotion_game.npc_describe_emotion import npc_describe_emotion
from emotion_game.player_guess import player_guess
from emotionGameQueries import assign_next_emotion
import openAIqueries
from openAIqueries import extract_player_name
from llm_client import client
from streamNPCresponse.streamTextResponse import streamResponse
from turnContext import EmotionGameTurn
from emotionGameQueries import get_active_emotion, get_remaining_emotions, update_share_story, append_game_md_log
from db import get_cursor

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------------
# config
# -----------------------------------------------------------------------------------
idUser  = 1
idNPC   = 1
currentScene = """
    GAME SCENARIO
    -------------
    - You have lost your ability to name your emotions
    - You are aware that something emotional is happening internally
    - You cannot yet access or describe what it feels like
    - You can describe emotions through thoughts, body sensations, and behavior.
    - You need help from the player in identifying the emotion you are feeling
    - Finding the name for an emotion changes your internal state in a noticeable way
        (e.g., steadiness, quieting, release of tension, shift in focus, emotional containment).
    - Stay fully in character at all times.
    - Do not mention games, rules, prompts, or AI.
    - You must NEVER state or imply the name of the emotion.
    - You are strictly forbidden from using the following words, in any form or tense:
      happy, sad, angry, afraid, surprised, disgusted, calm, excited
    - Never begin a sentence with the word "This" by itself.
        Always use a clear noun phrase such as:
        "This feeling…", "What I'm feeling now…", or
        "The way my body feels right now…"
"""
from elevenlabsQueries import get_default_voice_id
voiceId = get_default_voice_id()  # single source of truth — see elevenlabsQueries.py
active_turns = {}  # this will be persistent for the lifetime of the socketio instance
turn = EmotionGameTurn(
    idUser=idUser,
    idNPC=idNPC,
    current_scene=currentScene,
    voiceId=voiceId,
    game_started=False,
    guessing_started=False,
    player_name="Gabriel"
)
active_turns[idUser] = turn

# -----------------------------------------------------------------------------------
# Game state machine — event-driven by Unreal socket events.
# -----------------------------------------------------------------------------------
def assignEmotion(turn, sio):
    emotion = assign_next_emotion(turn)
    if not emotion:
        turn.game_over = True
        player_guess(turn, sio)
        return
    turn.cues = openAIqueries.get_cues_for_emotion(
        emotion=emotion,
        client=client
    )
    npc_describe_emotion(turn, sio=sio)
    turn.guessing_started = True

# -----------------------------------------------------------------------------------
def start_game(sio):
    # Acquire the turn lock so no emotion clicks sneak in during intro
    if not turn._lock.acquire(blocking=False):
        logger.debug("[start_game] ignored — another turn in progress")
        return
    turn.turn_in_progress = True
    try:
        _start_game_impl(sio)
    finally:
        turn.turn_in_progress = False
        turn._lock.release()


def _start_game_impl(sio):

    # --- Cache NPC persona once so the 5 prompt builders don't each
    #     hit TiDB Cloud for the same row. ---
    from emotion_game.npc_data import get_npc
    turn._npc_data = get_npc(turn.idNPC)

    # the following two conditions are if the game has started
    # and the player walked away and came back
    # --- Clear stale player_text from previous session so it isn't
    #     replayed as a guess on reconnect. ---
    turn.player_text = ""

    with get_cursor(dictionary=True) as (db, cursor):
        cursor.execute("""
            SELECT
            CASE
                WHEN (SELECT COUNT(*) FROM emotion
                      WHERE emotion.idEmotion IN (
                          SELECT idEmotion FROM emotion_guess_game
                          WHERE idUser = %s AND idNPC = %s))
                     > 0
                AND (SELECT COUNT(*) FROM emotion_guess_game
                    WHERE idUser = %s AND idNPC = %s
                      AND guessed_correctly = 1)
                    = (SELECT COUNT(*) FROM emotion)
                THEN 1
                ELSE 0
            END AS all_emotions_guessed_correctly;
        """, (turn.idUser, turn.idNPC, turn.idUser, turn.idNPC))
        gameOver = cursor.fetchone()

    if gameOver["all_emotions_guessed_correctly"] == 1:
        turn.game_over = True
        player_guess(turn, sio)
        return

    # --- Reconnect during name-ask phase: NPC asked for player's name,
    #     player disconnected, come back and re-ask. ---
    if turn.waiting_for_name:
        # We can't know if the player already answered or not; safest is to
        # re-ask the name question.
        turn.game_started = False
        turn.guessing_started = False
        npc_introduce(turn, sio)
        return

    # --- Reconnect during pause-after-share: backend paused and
    #     is waiting for Unreal to emit 'game_continue'.  Re-emit
    #     game_pause so Unreal knows the paused state. ---
    if turn.waiting_for_continue:
        try:
            sio.emit("game_pause", {}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        return

    # --- Reconnect during share phase: player guessed correctly,
    #     NPC asked "have you ever felt X?", then player disconnected.
    #     No active emotion in DB, so restore the share prompt. ---
    if turn.waiting_for_share:
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        from phase_2_queries import update_NPC_user_memory_query
        from emotion_game.get_NPC_mem import getNPCmem

        turn.game_started = True
        turn.guessing_started = True
        sio.emit("game_start", {}, room=f"user:{turn.idUser}")
        sio.emit("remaining_emotions",
                {"remaining_emotions": get_remaining_emotions(turn)},
                room=f"user:{turn.idUser}")

        turn.npc_memory = getNPCmem(turn)
        turn.prompt = build_correct_guess_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client=client, sio=sio)
        try:
            sio.emit("npc_responded", {"text": turn.last_npc_text},
                    room=f"user:{turn.idUser}")
        except Exception:
            pass
        turn.npc_memory = (
            f"[You just responded to {turn.player_name} with:] "
            f"'{turn.last_npc_text}'"
        )
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
        return

    res = get_active_emotion(turn)
    if res:
        turn.cur_npc_emotion = res["emotion"]
        turn.game_started = True
        turn.guessing_started = True
        sio.emit("game_start", {}, room=f"user:{turn.idUser}")
        sio.emit("remaining_emotions", {"remaining_emotions": get_remaining_emotions(turn)}, room=f"user:{turn.idUser}")
        player_guess(turn, sio)
        return

    npc_introduce(turn, sio)

# -----------------------------------------------------------------------------------
def advance_game(turn, player_text, npc_text, sio):
    """Thread-safe wrapper: only one turn can run at a time."""
    if not turn._lock.acquire(timeout=5):
        logger.debug("[advance_game] ignored — another turn in progress (timeout)")
        return
    turn.turn_in_progress = True
    try:
        _advance_game_impl(turn, player_text, npc_text, sio)
    finally:
        turn.turn_in_progress = False
        turn._lock.release()


def continue_game(turn, sio):
    """Called when Unreal emits 'game_continue' after the post-share pause.
    
    A new player has walked up — NPC introduces itself and asks their name.
    After the name is received, the NPC jumps straight to describing the
    next emotion (skipping the agreement phase)."""
    if not turn._lock.acquire(timeout=5):
        logger.debug("[continue_game] ignored — lock held (timeout)")
        return
    turn.turn_in_progress = True
    try:
        if not turn.waiting_for_continue:
            logger.debug("[continue_game] ignored — not waiting for continue")
            return
        turn.waiting_for_continue = False

        # Reset for new player: skip full intro, just ask for name then go.
        # Clear old NPC memory so the previous player's stories don't leak.
        turn.npc_memory = ""
        from phase_2_queries import update_NPC_user_memory_query
        update_NPC_user_memory_query(turn.idNPC, turn.idUser,
                                    "[New player joined — memory reset]")
        turn.game_started = False
        turn.guessing_started = False
        turn.name_ask_from_continue = True

        npc_introduce(turn, sio)
    finally:
        turn.turn_in_progress = False
        turn._lock.release()


def _advance_game_impl(turn, player_text, npc_text, sio):

    turn.player_text = player_text
    turn.last_npc_text = npc_text

    # -------- GAME PAUSED (waiting for Unreal to continue) --------
    if turn.waiting_for_continue:
        # Game is paused; ignore player input
        return

    # -------- PLAYER NAME PHASE --------
    if turn.waiting_for_name:
        # Player just told us their name — extract it with LLM
        name = extract_player_name(player_text, client)
        if not name or not name.strip():
            # No name found — ask again
            logger.info(f"[name-extract] no name in '{player_text}', re-asking")
            try:
                sio.emit("npc_responded",
                        {"text": "I'm sorry, I didn't quite hear your name. What should I call you?"},
                        room=f"user:{turn.idUser}")
            except Exception:
                pass
            return
        turn.player_name = name
        turn.waiting_for_name = False
        # After a game_continue name ask, skip the full intro and go
        # straight to describing the next emotion.
        if turn.name_ask_from_continue:
            turn.name_ask_from_continue = False
            turn.game_started = True
            turn.guessing_started = False
            # Remind NPC to greet the new player by name before describing
            # the emotion (they skipped the full intro phase).
            turn.npc_memory = (
                f"[NOTE: A new player named {turn.player_name} is here. "
                f"Greet them warmly by name before you start describing "
                f"what you're feeling right now.]"
            )
            from phase_2_queries import update_NPC_user_memory_query
            update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
            try:
                sio.emit("game_start", {}, room=f"user:{turn.idUser}")
                sio.emit("remaining_emotions",
                        {"remaining_emotions": get_remaining_emotions(turn)},
                        room=f"user:{turn.idUser}")
            except Exception:
                pass
            assignEmotion(turn, sio)
            return
        # NPC already explained their dilemma and asked for name in the
        # intro — skip the agreement and go straight to the game.
        # Add a greeting note so the NPC acknowledges the player by name
        # before describing the first emotion.
        turn.npc_memory = (
            f"[NOTE: You just learned the player's name is {turn.player_name}. "
            f"Greet {turn.player_name} warmly by name before you start "
            f"describing what you're feeling right now.]"
        )
        from phase_2_queries import update_NPC_user_memory_query
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        turn.game_started = True
        turn.guessing_started = False
        append_game_md_log(turn, "start",
                          f"Game started! Player **{turn.player_name}** is helping "
                          f"NPC {turn.idNPC} identify their emotions.")
        sio.emit("game_start", {}, room=f"user:{turn.idUser}")
        sio.emit("remaining_emotions",
                {"remaining_emotions": get_remaining_emotions(turn)},
                room=f"user:{turn.idUser}")
        assignEmotion(turn, sio)
        return

    # -------- SHARE EXPERIENCE PHASE --------
    if turn.waiting_for_share:
        # Player shared their experience — thank them, then move on
        from emotion_game.build_share_response_prompt import build_share_response_prompt
        from phase_2_queries import update_NPC_user_memory_query
        from emotion_game.get_NPC_mem import getNPCmem

        turn.npc_memory = f"{turn.player_name} shared about a time they felt {turn.last_correct_emotion}: {turn.player_text}"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        # persist the share story against the latest correct guess attempt
        update_share_story(turn, share_story=turn.player_text)

        turn.npc_memory = getNPCmem(turn)

        turn.prompt = build_share_response_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client=client, sio=sio)
        print("\nNPC SHARE RESPONSE:", turn.last_npc_text)

        append_game_md_log(turn, "share",
                          f"{turn.player_name} shared about feeling **{turn.last_correct_emotion}**:\n\n"
                          f"> {turn.player_text}\n\n"
                          f"NPC: _{turn.last_npc_text}_")

        turn.npc_memory = f"[You just responded to {turn.player_name} with:] '{turn.last_npc_text}'"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        try:
            sio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass

        # reset share state before moving on
        prev_emotion = turn.last_correct_emotion
        turn.waiting_for_share = False
        turn.last_correct_emotion = ""

        # --- boundary note: prevent LLM from contaminating the next
        #     emotion with cues / descriptions from the previous one ---
        turn.npc_memory = (
            f"[NOTE: You resolved the {prev_emotion} feeling. "
            f"A brand new, different feeling is here now. "
            f"Do NOT mention, describe, or reference {prev_emotion} at all. "
            f"Focus completely on what you are feeling right now.] "
            f"{turn.npc_memory}"
        )
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        # --- pause: wait for Unreal to emit game_continue ---
        turn.waiting_for_continue = True
        try:
            sio.emit("game_pause", {}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        return

    # -------- AGREEMENT PHASE --------
    if not turn.game_started:

        if not agree_check(turn):
            player_disagreed(turn, sio=sio)
            return

        turn.game_started = True
        turn.guessing_started = False
        append_game_md_log(turn, "start",
                          f"Game started! Player **{turn.player_name}** agreed to help "
                          f"NPC {turn.idNPC} identify their emotions.")
        sio.emit("game_start", {}, room=f"user:{turn.idUser}")
        sio.emit("remaining_emotions", {"remaining_emotions": get_remaining_emotions(turn)}, room=f"user:{turn.idUser}")

    # -------- ASSIGN / DESCRIBE --------
    if not turn.guessing_started:
        assignEmotion(turn, sio)
        return

    # -------- PLAYER GUESS --------
    turn.player_text = player_text
    res = player_guess(turn, socketio=sio)

    if res["status"] == "CorrectAskShare":
        # NPC already streamed the "thanks + ask to share" response.
        # waiting_for_share is set; just return and wait for player input.
        return
    if res["status"] == "False":
        return

    if res["status"] == "Other":
        return

    if res["status"] == "End":
        return
