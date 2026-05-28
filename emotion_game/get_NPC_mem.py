import mysql.connector
from turnContext import EmotionGameTurn
from db import connect
#---------------------------------------------------------------------------------
def getNPCmem(t : EmotionGameTurn):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor() 
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
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return ""
    finally:
        cursor.close()
        db.close()