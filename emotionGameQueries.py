from turnContext import EmotionGameTurn
from db import get_cursor

# ------------------------------------------------------------------
def mark_emotion_guessed_correct(t: EmotionGameTurn):
    with get_cursor() as (db, cursor):
        cursor.execute("""
            UPDATE emotion_guess_game
            SET guessed_correctly = 1,
                active = 0,
                completedAt = NOW()
            WHERE idUser = %s
            AND idNPC = %s
            AND active = 1;
        """, (t.idUser, t.idNPC))
        db.commit()

# ------------------------------------------------------------------
def get_remaining_emotions(t: EmotionGameTurn) -> list[str]:
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute("""
            SELECT e.emotion
            FROM emotion e
            WHERE e.idEmotion NOT IN (
                SELECT g.idEmotion
                FROM emotion_guess_game g
                WHERE g.idUser = %s
                  AND g.idNPC = %s
                  AND g.guessed_correctly = 1
            )
            ORDER BY e.idEmotion ASC;
        """, (t.idUser, t.idNPC))
        rows = cursor.fetchall()
        return [r["emotion"] for r in rows]

# ------------------------------------------------------------------
def get_active_emotion(t: EmotionGameTurn) -> dict | None:
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute("""
            SELECT e.idEmotion, e.emotion
            FROM emotion_guess_game g
            JOIN emotion e ON e.idEmotion = g.idEmotion
            WHERE g.idUser = %s
              AND g.idNPC = %s
              AND g.active = 1
            LIMIT 1;
        """, (t.idUser, t.idNPC))
        return cursor.fetchone()

# ------------------------------------------------------------------
def get_num_correct(t: EmotionGameTurn) -> dict | None:
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute("""
            SELECT COUNT(*) AS num_correct
            FROM emotion_guess_game
            WHERE idUser = %s
              AND idNPC = %s
              AND guessed_correctly = 1;
        """, (t.idUser, t.idNPC))
        return cursor.fetchone()

# ------------------------------------------------------------------
def assign_next_emotion(t: EmotionGameTurn):
    with get_cursor(dictionary=True) as (db, cursor):

        # 1. Deactivate any currently active emotion (safety)
        cursor.execute("""
            UPDATE emotion_guess_game
            SET active = 0
            WHERE idUser = %s
              AND idNPC = %s
              AND active = 1;
        """, (t.idUser, t.idNPC))

        # 2. Find the next unused emotion (deterministic order!)
        cursor.execute("""
            SELECT e.idEmotion, e.emotion
            FROM emotion e
            LEFT JOIN emotion_guess_game g
              ON g.idEmotion = e.idEmotion
             AND g.idUser = %s
             AND g.idNPC = %s
            WHERE g.idEmotion IS NULL
            ORDER BY e.idEmotion ASC
            LIMIT 1;
        """, (t.idUser, t.idNPC))

        emotion = cursor.fetchone()
        if not emotion:
            db.commit()
            return None  # all emotions completed

        # 3. Insert as the new active emotion
        cursor.execute("""
            INSERT INTO emotion_guess_game (
                idUser,
                idNPC,
                idEmotion,
                active,
                described,
                guessed_correctly
            )
            VALUES (%s, %s, %s, 1, 1, 0);
        """, (t.idUser, t.idNPC, emotion["idEmotion"]))

        db.commit()
        return emotion
