from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
from phase_2_queries import update_NPC_user_memory_query
from streamNPCresponse.streamTextResponse import streamResponse
from emotionGameQueries import get_active_emotion
from llm_client import client
from turnContext import EmotionGameTurn


def npc_describe_emotion(turn: EmotionGameTurn, sio) -> str:
    try:
        # prompt for describing current emotion
        turn.prompt = build_describe_emotion_prompt(turn)
        # stream response from openAI
        turn.cur_npc_emotion = get_active_emotion(turn)["emotion"]

        sio.emit("current_emotion",
                turn.cur_npc_emotion,
                room=f"user:{turn.idUser}")

        print(f"\nCURRENT EMOTION {turn.cur_npc_emotion}\n")
        turn.last_npc_text = streamResponse(turn, client=client, sio=sio)
        # debug
        print("\nNPC DESCRIBE EMOTION RESPONSE: ", turn.last_npc_text)
        # update npcs kb with its own response
        turn.npc_memory = f"[You just responded to {turn.player_name} with:] '{turn.last_npc_text}'"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        try:
            sio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass

        return turn.last_npc_text

    except Exception as e:
        import traceback
        traceback.print_exc()
        return ""
