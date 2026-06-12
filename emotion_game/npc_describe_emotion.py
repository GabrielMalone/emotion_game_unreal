import logging

from emotion_game.build_describe_emotion_prompt import build_describe_emotion_prompt
from phase_2_queries import update_NPC_user_memory_query
from streamNPCresponse.streamTextResponse import streamResponse
from emotionGameQueries import get_active_emotion
from llm_client import client
from turnContext import EmotionGameTurn

logger = logging.getLogger(__name__)


def npc_describe_emotion(turn: EmotionGameTurn, sio) -> str:
    try:
        # fetch active emotion BEFORE building prompt so we can pass category guidance
        active = get_active_emotion(turn)
        if not active:
            logger.error("npc_describe_emotion called with no active emotion — aborting")
            return ""
        turn.cur_npc_emotion = active.get("emotion", "")

        # prompt for describing current emotion
        turn.prompt = build_describe_emotion_prompt(turn)

        sio.emit("current_emotion",
                turn.cur_npc_emotion,
                room=f"user:{turn.idUser}")

        logger.debug(f"CURRENT EMOTION {turn.cur_npc_emotion}")
        turn.last_npc_text = streamResponse(turn, client=client, sio=sio)
        # debug
        logger.debug(f"NPC DESCRIBE EMOTION RESPONSE: {turn.last_npc_text}")
        # update npcs kb with its own response
        turn.npc_memory = f"[You just responded to {turn.player_name} with:] '{turn.last_npc_text}'"
        update_NPC_user_memory_query(turn.idNPC, turn.idUser, turn.npc_memory)

        try:
            sio.emit("npc_responded", {"text": turn.last_npc_text}, room=f"user:{turn.idUser}")
        except Exception:
            pass

        return turn.last_npc_text

    except Exception:
        logger.exception("npc_describe_emotion crashed")
        return ""
