import mysql.connector
from turnContext import EmotionGameTurn
from db import connect
#------------------------------------------------------------------
def mark_emotion_guessed_correct(t: EmotionGameTurn):
    db = connect()
    try:
        cursor = db.cursor()
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
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_active_emotion(t: EmotionGameTurn) -> dict | None:
    db = connect()
    try:
        cursor = db.cursor(dictionary=True)
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
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return None
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_num_correct(t: EmotionGameTurn) -> dict | None:
    db = connect()
    try:
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT COUNT(*) AS num_correct
            FROM emotion_guess_game
            WHERE idUser = %s
              AND idNPC = %s
              AND guessed_correctly = 1;
        """, (t.idUser, t.idNPC))

        return cursor.fetchone()

    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return None
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def assign_next_emotion(t: EmotionGameTurn):
    db = connect()
    try:
        cursor = db.cursor(dictionary=True)

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

    except mysql.connector.Error as err:
        db.rollback()
        print("MySQL Error:", err)
        return None

    finally:
        cursor.close()
        db.close()