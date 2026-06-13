from flask import jsonify
from db import get_cursor


def update_NPC_user_memory_query(idNPC: int, idUser: int, kbText: str):
    """Append to NPC memory, keeping only the last 10 entries."""
    MAX_ENTRIES = 10

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

        # Read back, prune to last MAX_ENTRIES blocks
        cursor.execute(
            "SELECT kbText FROM npc_user_memory WHERE idNPC = %s AND idUser = %s",
            (idNPC, idUser),
        )
        full = cursor.fetchone()[0] or ""
        blocks = [b for b in full.split("\n\n[") if b.strip()]
        if len(blocks) > MAX_ENTRIES:
            pruned = "\n\n[" + "\n\n[".join(blocks[-MAX_ENTRIES:])
            cursor.execute(
                "UPDATE npc_user_memory SET kbText = %s WHERE idNPC = %s AND idUser = %s",
                (pruned, idNPC, idUser),
            )
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
