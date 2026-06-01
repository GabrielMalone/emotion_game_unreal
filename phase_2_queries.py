from flask import jsonify
from db import get_cursor


def update_NPC_user_memory_query(idNPC: int, idUser: int, kbText: str):
    with get_cursor() as (db, cursor):
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
        cursor.execute(query, (idNPC, idUser, kbText))
        db.commit()
        return jsonify({"status": "success"}), 200


def get_NPC_user_memory_query(idUser: int, idNPC: int):
    with get_cursor(dictionary=True) as (_db, cursor):
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
