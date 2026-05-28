from flask import jsonify
import mysql.connector
from turnContext import EmotionGameTurn
from db import connect

#------------------------------------------------------------------
def update_NPC_user_memory_query(t: EmotionGameTurn):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor()
        query = """
            INSERT INTO npc_user_memory (idNPC, idUser, kbText, updatedAt)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                kbText = CONCAT(
                    IFNULL(kbText, ''),
                    '\n\n[',
                    NOW(),
                    '] ',
                    VALUES(kbText)
                ),
                updatedAt = NOW();
        """
        cursor.execute(query, (t.idNPC, t.idUser, t.npc_memory))
        db.commit()
        return jsonify({"status": "success"}), 200
    except mysql.connector.Error as err:
        db.rollback()
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()

#------------------------------------------------------------------
def get_NPC_user_memory_query(idUser: int, idNPC: int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT
          kbText,
          updatedAt
        FROM npc_user_memory
        WHERE idNPC = %s
          AND idUser = %s
        """
        cursor.execute(query, (idNPC, idUser))
        row = cursor.fetchone()
        return jsonify({"memory": row}), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
