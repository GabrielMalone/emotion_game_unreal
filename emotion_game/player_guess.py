import logging

from phase_2_queries import update_NPC_user_memory_query
from streamNPCresponse.streamTextResponse import streamResponse
import openAIqueries
from emotion_game.build_incorrect_prompt import build_incorrect_prompt
from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
from llm_client import client
from turnContext import EmotionGameTurn
from emotionGameQueries import mark_emotion_guessed_correct, get_active_emotion, get_num_correct, get_remaining_emotions, log_guess_attempt, append_game_md_log
from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
from emotion_game.get_NPC_mem import getNPCmem

logger = logging.getLogger(__name__)


def player_guess(turn: EmotionGameTurn, socketio) -> dict:

    # categorize player's emotion guess
    turn.emotion_guessed = openAIqueries.classify_emotion_guess(turn, client)
    logger.debug(f"PLAYER GUESSED: {turn.emotion_guessed} by saying {turn.player_text}")

    # this means player has correctly guessed all emotions
    # could either end game at this point
    # or increase to next difficulty level
    if turn.game_over:
        logger.debug("ALL EMOTIONS ANSWERED!")
        append_game_md_log(turn, "round_end",
                          f"All emotions guessed correctly! Round complete.")
        turn.npc_memory = f"{turn.player_name} correctly identified all of your emotions and completed the round"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
        turn.npc_memory = getNPCmem(turn)
        turn.prompt = build_end_round_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client, sio=socketio)
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        return {"status": "End"}

    # otherwise check to see if the emotion guessed is the correct one
    data = get_active_emotion(turn)
    npc_emotion = data["emotion"]
    npc_emotion_guessed_id = data["idEmotion"]
    logger.debug(f"ACTIVE NPC EMOTION: {npc_emotion}")

    # if player did something other than make a guess
    # and this is not the intro conversation
    if turn.emotion_guessed is None and turn.game_started:
        logger.debug(f"OTHER THAN GUESS BRANCH on statement {turn.player_text}")
        turn.npc_memory = f"{turn.player_name} just made a statement that was not a guess: {turn.player_text}"
        if turn.player_text:
            update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
        turn.npc_memory = getNPCmem(turn)
        turn.cues = openAIqueries.get_cues_for_emotion(npc_emotion, client=client)
        turn.prompt = build_no_guess_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client, sio=socketio)
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        log_guess_attempt(turn, player_guess=turn.player_text, correct=False,
                          feedback_text=turn.last_npc_text)
        append_game_md_log(turn, "statement",
                          f"{turn.player_name} said: _{turn.player_text}_\n\nNPC: _{turn.last_npc_text}_")
        return {"status": "Other"}

    if turn.emotion_guessed == npc_emotion:
        # mark correct in database
        logger.debug(f"CORRECT! {npc_emotion} == {turn.emotion_guessed}")
        turn.emotion_guessed_id = npc_emotion_guessed_id
        mark_emotion_guessed_correct(turn)
        num_correct = get_num_correct(turn)
        try:
            socketio.emit("correct", num_correct)
        except Exception:
            pass
        try:
            remaining = get_remaining_emotions(turn)
            socketio.emit("remaining_emotions", {"remaining_emotions": remaining}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        # update npc memory about this event
        turn.npc_memory = f"{turn.player_name} said: {turn.player_text}. As a result {turn.player_name} correctly identified your emotion {turn.emotion_guessed}"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
        turn.npc_memory = getNPCmem(turn)

        # --- stream the "correct guess" prompt (thanks + ask to share) ---
        from emotion_game.build_correct_guess_prompt import build_correct_guess_prompt
        turn.prompt = build_correct_guess_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client=client, sio=socketio)
        logger.debug(f"NPC CORRECT GUESS RESPONSE: {turn.last_npc_text}")
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass

        # update memory with NPC's response to the correct guess
        turn.npc_memory = f"[You just responded to {turn.player_name} with:] '{turn.last_npc_text}'"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        # log the correct guess to the database
        log_guess_attempt(turn, player_guess=turn.player_text, correct=True,
                          feedback_text=turn.last_npc_text)

        append_game_md_log(turn, "correct",
                          f"Guessed: **{npc_emotion}** (correct)\n\n"
                          f"{turn.player_name} said: _{turn.player_text}_\n\n"
                          f"NPC: _{turn.last_npc_text}_")

        # set state: wait for player to share their experience
        turn.waiting_for_share = True
        turn.last_correct_emotion = npc_emotion

        return {"status": "CorrectAskShare"}

    else:
        logger.debug(f"INCORRECT! {turn.emotion_guessed} != {npc_emotion}")
        turn.npc_memory = f"{turn.player_name} said: {turn.player_text}. As a result {turn.player_name} incorrectly identified your emotion {turn.emotion_guessed}"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
        turn.cues = openAIqueries.get_cues_for_emotion(npc_emotion, client=client)
        turn.prompt = build_incorrect_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client=client, sio=socketio)
        # debug
        logger.debug(f"NPC RESPONDED TO INCORRECT GUESS: {turn.last_npc_text}")
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        log_guess_attempt(turn, player_guess=turn.player_text, correct=False,
                          feedback_text=turn.last_npc_text)
        append_game_md_log(turn, "incorrect",
                          f"Guessed: **{turn.emotion_guessed}** (incorrect, actual: _{npc_emotion}_)\n\n"
                          f"{turn.player_name} said: _{turn.player_text}_\n\n"
                          f"NPC: _{turn.last_npc_text}_")
        return {"status": "False"}
