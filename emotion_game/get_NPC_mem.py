from turnContext import EmotionGameTurn
from db import get_cursor


def getNPCmem(t: EmotionGameTurn) -> str:
    with get_cursor() as (_db, cursor):
        query = """
        SELECT
            kbText,
            updatedAt
        FROM npc_user_memory
        WHERE idNPC = %s
          AND idUser = %s
        """
        cursor.execute(query, (t.idNPC, t.idUser))
        row = cursor.fetchone()
        return row[0] if row else ""
