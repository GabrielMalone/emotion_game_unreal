from flask import request, jsonify
import mysql.connector
from turnContext import EmotionGameTurn
from db import connect

#------------------------------------------------------------------
def update_NPC_user_memory_query(t : EmotionGameTurn):
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
def get_choice_content_query(idChoice:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True) 
        query = """
        SELECT
            choiceText
        FROM choice
        WHERE idChoice = %s
        """
        cursor.execute(query, (idChoice,))
        row = cursor.fetchone()
        print(f"\ncur choice content: {row}\n")
        return jsonify({ "choiceContent": row }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()     
#------------------------------------------------------------------
def get_NPC_user_memory_query(idUser:int, idNPC:int):
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
        cursor.execute(query, (idNPC,idUser))
        row = cursor.fetchone()
        # print(f"\nget NPC {idNPC} memory: {row}\n")
        return jsonify({ "memory": row }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()  
#------------------------------------------------------------------
def get_inventory_query(idUser:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)  # good for making JSON 
        query = """
        SELECT 
            i.itemName,
            u.quantity
        FROM userItem AS u
        JOIN item AS i
            ON u.idItem = i.idItem
        WHERE u.idUser = %s;
        """
        cursor.execute(query, (idUser,))
        rows = cursor.fetchall()
        print(f"\nget inventory: {rows}\n")
        return jsonify({ "inventory": rows }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
# This will load the next available storylet for a player from one NPC
#------------------------------------------------------------------
# give the next available storylet for a specific NPC and user,
# that the user has NOT completed yet,
# and whose preconditions are either nonexistent or all satisfied.
def get_avail_storylets_query(idUser:int, idNPC:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT 
            s.idStorylet, s.nameStorylet, s.contentStorylet 
        FROM 
            storylet s 
        LEFT JOIN 
            storylet_preconditions sp ON sp.idStorylet = s.idStorylet 
        LEFT JOIN 
            user_precondition up ON up.idPrecondition = sp.idPrecondition AND up.idUser = %s
        LEFT JOIN 
            completedStorylet cs ON cs.idStorylet = s.idStorylet AND cs.idUser = %s
        WHERE 
            s.idNPC = %s AND cs.idStorylet IS NULL 
        GROUP BY s.idStorylet, s.nameStorylet HAVING COUNT(sp.idPrecondition) = 0 
        OR SUM(up.conditionMet = 1) = COUNT(sp.idPrecondition) 
        ORDER BY 
            s.idStorylet 
        ASC LIMIT 1;
        """
        cursor.execute(query, (idUser, idUser, idNPC))
        row = cursor.fetchone()
        print(f"\nstorylet: {row}\n")
        return jsonify({ "storylets": row }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_NPC_BG_query(idNPC:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT BGcontent FROM background WHERE idNPC = %s
        """
        cursor.execute(query, (idNPC,))
        row = cursor.fetchone()
        # print(f"\nnpc {idNPC} background: {row}\n")
        return jsonify({ "background": row }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_user_NPC_rel_query(idUser:int, idNPC:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT
            rt.typeRelationship        AS relationshipType,
            r.trust                    AS trust,
            r.relTypeIntensity         AS intensity
        FROM playerNPCrelationship r
        JOIN relationshipType rt
            ON r.idRelationshipType = rt.idRelationshipType
        WHERE r.idUser = %s
        AND r.idNPC  = %s;
        """
        cursor.execute(query, (idUser,idNPC))
        row = cursor.fetchone()
        # print(f"\nuser {idUser} npc {idNPC} relationship: {row}\n")
        return jsonify({ "rel_info": row}), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_storylet_choices_query(idStorylet:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
          SELECT
            idChoice,
            choiceText
        FROM choice
        WHERE idSourceStorylet = %s;
        """
        cursor.execute(query, (idStorylet,))
        rows = cursor.fetchall()
        print(f"\nchoice: {rows}\n")
        return jsonify({"choices": rows}), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_NPC_emotion_query(idNPC:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT
            n.nameFirst          AS name,
            e.emotion            AS emotion,
            ne.emotionIntensity  AS intensity
        FROM npcEmotion ne
        JOIN emotion e
            ON ne.idEmotion = e.idEmotion
        JOIN NPC n
            ON ne.idNPC = n.idNPC
        WHERE ne.idNPC = %s;
        """
        cursor.execute(query, (idNPC,))
        row = cursor.fetchone()
        cursor.fetchall()  # IMPORTANT
        print(f"\nnpc {idNPC} cur emotion: {row}\n")
        return jsonify({ "emotion_info": row }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def get_user_tasks_query(idUser:int):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor(dictionary=True)
        query = """
        SELECT
            t.idTask,
            t.taskName,
            t.taskDetails,
            n.idNPC,
            n.nameFirst AS npcName,
            ut.startedAt
        FROM user_task ut
        JOIN tasks t
        ON ut.idTask = t.idTask
        JOIN NPC n
        ON t.idNPC = n.idNPC
        WHERE ut.idUser = %s
        AND ut.status = 'active'
        ORDER BY ut.startedAt ASC;
        """
        cursor.execute(query, (idUser,))
        rows = cursor.fetchall()
        print(f"\nuser tasks: {rows}\n")
        return jsonify({ "user_tasks": rows }), 200
    except mysql.connector.Error as err:
        print("MySQL Error:", err)
        return jsonify({"status": "error"}), 500
    finally:
        cursor.close()
        db.close()    
#------------------------------------------------------------------
# start a relationship as stranger with 50 trust
def init_user_NPC_rel_query(idUser:int, idNPC:int):

    print(f"\nstarting relationship: {idUser} and {idNPC}\n")

    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor()
        query = """
        INSERT INTO playerNPCrelationship
        (idUser, idNPC, idRelationshipType, relTypeIntensity, trust)
        VALUES
        (%s, %s, 2, 0, 50);
        """
        cursor.execute(query, (idUser, idNPC))
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
# resultts of idChoice1:
# 1 - player becomes acquaintance with Adwin
# 2 - player completes storylet1
# 3 - player meets precondtion of 'adwin_met'
#------------------------------------------------------------------
def idChoice_1_query(idUser:int, idNPC:int, idStorylet:int):

    print(f"\nidChoice3_query: idUser:{idUser} idNPC: {idNPC} idCurStorylet: {idStorylet}\n")

    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor()
        query = """
        UPDATE playerNPCrelationship
        SET
            idRelationshipType = 4,
            relTypeIntensity   = 0,
            trust              = 50
        WHERE
            idUser = %s
        AND
            idNPC  = %s;
        """
        cursor.execute(query, (idUser, idNPC))
        query2 = """
        INSERT IGNORE INTO completedStorylet
        (idStorylet, idUser)
        VALUES
        (%s, %s);
        """
        cursor.execute(query2, (idStorylet, idUser))
        query3 = """
        UPDATE user_precondition up
        JOIN precondition p
        ON p.idPrecondition = up.idPrecondition
        SET
        up.conditionMet = 1
        WHERE
        up.idUser = %s
        AND
        p.nameCondition = %s;
        """
        cursor.execute(query3, (idUser, "adwin_met"))
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
# results of idChoice2:
# 1 - player gains some trust with Adwin
# 2 - player completes storylet2
# 3 - player meets precondtion of 'conflict_discovered'
# 4 - add task find_flowers to player's tasks
#------------------------------------------------------------------
def idChoice_3_query(idUser:int, idNPC:int, idStorylet:int):

    print(f"\nidChoice3_query: idUser:{idUser} idNPC: {idNPC} idCurStorylet: {idStorylet}\n")

    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor()
        # instead of hard coding 60, will need to get original trust 
        # #and do + 10 or whatever
        query = """
        UPDATE playerNPCrelationship
        SET
            idRelationshipType = 4,
            relTypeIntensity   = 0,
            trust              = 60
        WHERE
            idUser = %s
        AND
            idNPC  = %s;
        """
        cursor.execute(query, (idUser, idNPC)) 
        query2 = """
        INSERT IGNORE INTO completedStorylet
        (idStorylet, idUser)
        VALUES
        (%s, %s);
        """
        cursor.execute(query2, (idStorylet, idUser))
        query3 = """
        UPDATE user_precondition up
        JOIN precondition p
        ON p.idPrecondition = up.idPrecondition
        SET
        up.conditionMet = 1
        WHERE
        up.idUser = %s
        AND
        p.nameCondition = %s;
        """
        cursor.execute(query3, (idUser, "conflict_discovered"))
        query4 = """
        INSERT IGNORE INTO user_task (idTask, idUser, status)
        VALUES (
        (SELECT idTask
        FROM tasks
        WHERE taskName = 'find_flowers'
            AND idNPC = (SELECT idNPC FROM NPC WHERE nameFirst = 'Adwin')),
        %s,
        'active'
        );
        """ 
        cursor.execute(query4, (idUser,))
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
def update_trust(idUser, idNPC, delta):
    db = connect()
    if not db.is_connected():
        return
    try:
        cursor = db.cursor()
        cursor.execute("""
            UPDATE playerNPCrelationship
            SET trust = LEAST(100, GREATEST(0, trust + %s))
            WHERE idUser = %s AND idNPC = %s
            """, 
            (delta, idUser, idNPC))
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
def set_npc_emotion(idNPC, emotion_name, intensity):
    db = connect()
    if not db.is_connected():
        return

    try:
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT idEmotion FROM emotion WHERE emotion = %s
        """, (emotion_name,))

        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Emotion '{emotion_name}' not found")

        idEmotion = row["idEmotion"]

        cursor.execute("""
            INSERT INTO npcEmotion (idNPC, idEmotion, emotionIntensity)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
            emotionIntensity = %s
        """, (idNPC, idEmotion, intensity, intensity))

        db.commit()

    except mysql.connector.Error as err:
        db.rollback()
        print("MySQL Error:", err)

    finally:
        cursor.close()
        db.close()
#------------------------------------------------------------------
def decay_npc_emotions(idNPC, decay=0.9):
    if idNPC is None:
        print("[DECAY] idNPC is None, skipping")
        return

    db = connect()
    if not db.is_connected():
        return

    try:
        cursor = db.cursor()

        cursor.execute(
            """
            UPDATE npcEmotion
            SET emotionIntensity = emotionIntensity * %s
            WHERE idNPC = %s
            """,
            (decay, idNPC)
        )

        db.commit()
        print(f"[DECAY] Applied decay {decay} to NPC {idNPC}")

    except mysql.connector.Error as err:
        db.rollback()
        print("[DECAY] MySQL Error:", err)

    finally:
        cursor.close()
        db.close()