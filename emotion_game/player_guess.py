from phase_2_queries import update_NPC_user_memory_query
from streamNPCresponse.streamTextResponse import streamResponse
import openAIqueries
from emotion_game.build_incorrect_prompt import build_incorrect_prompt
from emotion_game.build_answered_all_correctly_prompt import build_end_round_prompt
from flask import request
from llm_client import client
from turnContext import EmotionGameTurn
from emotionGameQueries import mark_emotion_guessed_correct, get_active_emotion, get_num_correct
from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
from emotion_game.build_did_not_make_guess_prompt import build_no_guess_prompt
from emotion_game.get_NPC_mem import getNPCmem

def player_guess(turn: EmotionGameTurn, socketio) -> str:

    # categorize player's emotion guess
    turn.emotion_guessed = openAIqueries.classify_emotion_guess(turn, client)
    print(f"\nPLAYER GUESSED: {turn.emotion_guessed} by saying {turn.player_text}")
    
    # this means player has correctly guessed all emotions
    # could either end game at this point
    # or increase to next difficulty level
    if turn.game_over:
        print("\nALL EMOTIONS ASNWERED!\n")
        turn.npc_memory = f"{turn.player_name} correctly identified all of your emotions and completed the round {turn.emotion_guessed}"
        update_NPC_user_memory_query(turn)
        turn.npc_memory = getNPCmem(turn)
        turn.prompt = build_end_round_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client, sio=socketio)
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        return {"status" : "End"}
    
    # otherwise check to see if the emotion guessed is the correct one
    data = get_active_emotion(turn)
    npc_emotion = data["emotion"]
    npc_emotion_guessed_id = data["idEmotion"]
    print(f"\nACTIVE NPC EMOTION: {npc_emotion}\n")

    # if player did something other than make a guess 
    # and this is not the intro conversation
    if (turn.emotion_guessed is None and turn.game_started):
        print(f"\nOTHER THAN GUESS BRANCH on statement {turn.player_text}\n")
        turn.npc_memory = f"{turn.player_name} just made a statement that was not a guess: {turn.player_text}"
        if (turn.player_text):
            update_NPC_user_memory_query(turn)
        turn.npc_memory = getNPCmem(turn)
        turn.cues = openAIqueries.get_cues_for_emotion(npc_emotion, client=client)
        turn.prompt = build_no_guess_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client, sio=socketio)
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        return {"status" : "Other"}

    if (turn.emotion_guessed == npc_emotion):
        # mark correct in database
        print(f"CORRECT! {npc_emotion} == {turn.emotion_guessed}")
        turn.emotion_guessed_id = npc_emotion_guessed_id
        mark_emotion_guessed_correct(turn)
        num_correct = get_num_correct(turn)
        try:
            socketio.emit("correct", num_correct)
        except Exception:
            pass
        # update npc memory about this event
        turn.npc_memory = f"{turn.player_name} said: {turn.player_text}. As a result {turn.player_name} correctly identified your emotion {turn.emotion_guessed}"
        update_NPC_user_memory_query(turn)
        turn.npc_memory = getNPCmem(turn)
        return {"status" : "True", "turnData" : turn}

    else: 
        print(f"INCORRECT! {turn.emotion_guessed} != {npc_emotion}  ")
        turn.npc_memory = f"{turn.player_name} said: {turn.player_text}. As a result {turn.player_name} incorrectly identified your emotion {turn.emotion_guessed}"
        update_NPC_user_memory_query(turn)
        turn.cues = openAIqueries.get_cues_for_emotion(npc_emotion, client=client)
        turn.prompt = build_incorrect_prompt(turn)
        turn.last_npc_text = streamResponse(turn, client=client, sio=socketio)
        # debug
        print("\nNPC RESPONDED TO INCORRECT GUESS:", turn.last_npc_text)
        try:
            socketio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass
        return {"status" : "False"}
    
