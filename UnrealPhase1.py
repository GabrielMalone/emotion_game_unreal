from emotion_game.npc_introduce import npc_introduce, agree_check, player_disagreed
from emotion_game.npc_describe_emotion import npc_describe_emotion
from emotion_game.player_guess import player_guess
from emotionGameQueries import assign_next_emotion
import openAIqueries
from llm_client import client
from turnContext import EmotionGameTurn
from emotionGameQueries import get_active_emotion
from db import connect, get_cursor
# -----------------------------------------------------------------------------------
# config
# -----------------------------------------------------------------------------------
idUser  = 1
idNPC   = 1
currentScene = """
    GAME SCENARIO
    -------------
    - You have lost your ability to name your emotions
    - You are aware that something emotional is happening internally
    - You cannot yet access or describe what it feels like
    - You can describe emotions through thoughts, body sensations, and behavior.
    - You need help from the player in identifying the emotion you are feeling
    - Finding the name for an emotion changes your internal state in a noticeable way
        (e.g., steadiness, quieting, release of tension, shift in focus, emotional containment).
    - Stay fully in character at all times.
    - Do not mention games, rules, prompts, or AI.
    - You must NEVER state or imply the name of the emotion.
    - You are strictly forbidden from using the following words, in any form or tense:
      happy, sad, angry, afraid, surprised, disgusted, calm, excited
    - Never begin a sentence with the word "This" by itself.
        Always use a clear noun phrase such as:
        "This feeling…", "What I’m feeling now…", or
        "The way my body feels right now…"
"""
voiceId = "BIvP0GN1cAtSRTxNHnWS"
SERVER  = "http://localhost:5001"
active_turns = {} # this will be persistent for the lifetime of the socketio instance
turn = EmotionGameTurn(
    idUser=idUser,
    idNPC=idNPC,
    current_scene=currentScene,
    voiceId=voiceId,
    game_started=False,
    guessing_started=False,
    player_name="Gabriel"
)
active_turns[idUser] = turn
# -----------------------------------------------------------------------------------
# instead of a game loop, we now start the game with an overlap or whataver you wan
# event in unreal. Then we send this initializing data to the flask server
# and then that handles the db logic from there
# -----------------------------------------------------------------------------------
def assignEmotion(turn, sio):
    emotion = assign_next_emotion(turn)
    if not emotion:
        turn.game_over = True
        player_guess(turn, sio)
        return
    turn.cues = openAIqueries.get_cues_for_emotion(
        emotion=emotion,
        client=client
    )
    npc_describe_emotion(turn, sio=sio)
    turn.guessing_started = True
# -----------------------------------------------------------------------------------
def start_game(sio):

    # the following two conditions are if the game has started
    # and the player walked away and came back
    with get_cursor(dictionary=True) as (db, cursor):
        cursor.execute("""
            SELECT
            CASE
                WHEN COUNT(*) > 0
                AND COUNT(*) = SUM(guessed_correctly = 1)
                THEN 1
                ELSE 0
            END AS all_emotions_guessed_correctly
            FROM emotion_guess_game
            WHERE idUser = %s
            AND idNPC = %s;
        """, (turn.idUser, turn.idNPC))
        gameOver = cursor.fetchone()

    if gameOver["all_emotions_guessed_correctly"] == 1:
        turn.game_over = True
        player_guess(turn, sio)
        return
    
    res = get_active_emotion(turn)
    if res:    
        turn.cur_npc_emotion = res["emotion"]
        turn.game_started = True
        turn.guessing_started = True
        player_guess(turn, sio)
        return

    npc_introduce(turn, sio)
# -----------------------------------------------------------------------------------
def advance_game(turn, player_text, npc_text,sio):

    turn.player_text = player_text
    turn.last_npc_text = npc_text
    # -------- AGREEMENT PHASE --------
    if not turn.game_started:
        
        if not agree_check(turn):
            player_disagreed(turn, sio=sio)
            return

        turn.game_started = True
        turn.guessing_started = False

    # -------- ASSIGN / DESCRIBE --------
    if not turn.guessing_started:
        assignEmotion(turn, sio)
        return
 
    # -------- PLAYER GUESS --------
    turn.player_text = player_text
    res = player_guess(turn, socketio=sio)

    if res["status"] == "True":
        turn.npc_memory = res["turnData"].npc_memory
        assignEmotion(turn, sio)
        return
    if res["status"] == "False":
        return

    if res["status"] == "Other":
        return

    if res["status"] == "End":
        return
# -----------------------------------------------------------------------------------