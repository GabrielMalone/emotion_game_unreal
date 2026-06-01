from phase_2_queries import update_NPC_user_memory_query
from streamNPCresponse.streamTextResponse import streamResponse
import openAIqueries
from emotion_game.build_intro_prompt import build_intro_prompt
from emotion_game.build_disagree_prompt import build_disagree_prompt
from emotion_game.get_NPC_mem import getNPCmem
from llm_client import client
from turnContext import EmotionGameTurn


def npc_introduce(turn: EmotionGameTurn, sio):

    # start out worried for this scenario
    turn.cur_npc_emotion = "worried"
    # intro prompt for emotional eq game
    turn.prompt = build_intro_prompt(turn)
    # stream response from openAI
    r = streamResponse(turn, client=client, sio=sio)
    # debug
    print("\nNPC INTRO RESPONSE: ", r)
    # update npcs kb with its own response
    turn.npc_memory = f"[You just greeted {turn.player_name} with:] '{r}'"
    update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
    try:
        sio.emit("npc_responded", {"text": r}, room=f"user:{turn.idUser}")
    except Exception:
        pass  # socket already dead (walk-away / disconnect)


def agree_check(turn: EmotionGameTurn) -> bool:
    turn.npc_memory = getNPCmem(turn)
    return openAIqueries.classify_player_response_to_game_start(turn, client)


def player_disagreed(turn: EmotionGameTurn, sio):

    # update NPC's mem of player's response
    turn.npc_memory = f"[Player just disagreed to play with you by saying] '{turn.player_text}'"
    mem = getNPCmem(turn)
    update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)
    turn.npc_memory = mem
    turn.prompt = build_disagree_prompt(turn)
    turn.last_npc_text = streamResponse(turn, client=client, sio=sio)
    print("\nPLAYER's DISAGREEMENT: ", turn.player_text)
    try:
        sio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
    except Exception:
        pass
