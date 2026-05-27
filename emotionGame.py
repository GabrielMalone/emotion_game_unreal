import requests
from extensions import CamoClientExtension
from streamingMP3Player import StreamingMP3Player
import requests
from turnContext import EmotionGameTurn

# -----------------------------------------------------------------------------------
# config
# -----------------------------------------------------------------------------------
idUser = 1
idNPC = 1
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
voiceId = "ZF6FPAbjXT4488VcRRnw"  # Amelia — young British, enthusiastic & expressive
SERVER = "http://localhost:5001"
# -----------------------------------------------------------------------------------
# socket extension
# -----------------------------------------------------------------------------------
ext = CamoClientExtension(
    server_url=SERVER,
    idUser=idUser,
    make_player=lambda: StreamingMP3Player(),
)
ext.connect()
# -----------------------------------------------------------------------------------
def game_start()->bool:

    turn = EmotionGameTurn(
        idNPC=1,
        idUser=1,
        current_scene=currentScene,
        voiceId=voiceId
    )

    gameStarted = False

    while True:
        # ---------------------------------------------------------------------------
        #   introduction branch
        # ---------------------------------------------------------------------------
        if not gameStarted:
            turn.player_name = input("\n Enter your name: ").strip()

            requests.post(f"{SERVER}/npc_introduce", json={
                "idUser"        : turn.idUser,
                "idNPC"         : turn.idNPC,
                "currentScene"  : turn.current_scene,
                "playerName"    : turn.player_name,
                "idVoice"       : turn.voiceId,
            })

            # Wait until NPC finishes talking before allowing input
            ext.wait_for_npc_response(timeout=30)

            turn.player_text = input("\n Respond: ").strip()

            resp = requests.post(f"{SERVER}/player_agreed_check", json={
                "idUser"        : turn.idUser,
                "idNPC"         : turn.idNPC,
                "player_text"   : turn.player_text,
                "npcText"       : ext.last_npc_response,
                "idVoice"       : turn.voiceId,
            })
            agreed = resp.json().get("agreed", False)
        # ---------------------------------------------------------------------------
        # agreed to play branch
        # ---------------------------------------------------------------------------
        if agreed:

            guessingStarted = False
            gameStarted = True

            while True:

                # start guessing game 
                r = requests.post(f"{SERVER}/assign_next_emotion", json={
                        "idUser"        : turn.idUser,
                        "idNPC"         : turn.idNPC,
                        "pName"         : turn.player_name,
                        "curScene"      : turn.current_scene,
                        "npc_mem"       : turn.npc_memory,
                        "game_started"  : guessingStarted,
                        "player_text"   : turn.player_text,
                        "idVoice"       : turn.voiceId,

                    })
                
                # check if game over
                ne_data = r.json()
                game_status = ne_data.get("status")

                if game_status == "game_over":
                    print('game over')
                    resp = requests.post(f"{SERVER}/player_guess", json={
                        "idUser"        : turn.idUser,
                        "idNPC"         : turn.idNPC,
                        "playerName"    : turn.player_name,
                        "currentScene"  : turn.current_scene,
                        "player_text"   : turn.player_text,
                        "npcText"       : ext.last_npc_response,
                        "idVoice"       : turn.voiceId,
                        "game_started"  : False,
                        "game_over"     : True
                    })
                    ext.wait_for_npc_response(timeout=30)
                    return    
                
                # get player's guess for NPC's current emotion
                turn.player_text = input("\n\n Respond: ").strip()
                guessingStarted = True
                ext.npc_response_ready.clear()
                # check the guess
                resp = requests.post(f"{SERVER}/player_guess", json={
                        "idUser"        : turn.idUser,
                        "idNPC"         : turn.idNPC,
                        "playerName"    : turn.player_name,
                        "currentScene"  : turn.current_scene,
                        "player_text"   : turn.player_text,
                        "npcText"       : ext.last_npc_response,
                        "game_started"  : gameStarted,
                        "idVoice"       : turn.voiceId,
                        "game_over"     : False
                    })
                data = resp.json()
                result = data.get("res")
                # -------------------------------------------------------------------
                # correct guess branch
                # -------------------------------------------------------------------
                if result == "True":
                    print("\n\nCORCORRECT GUESS!\n\n")
                    turnData= data.get("turnData")
                    turn.npc_memory = turnData["npc_memory"]
                    turn.player_text = turnData["player_text"]                  
                # -------------------------------------------------------------------
                # other statement made branch
                # -------------------------------------------------------------------               
                while result == "Other":
                    print("\nother statement made\n")
                    turn.player_text = input("\n Respond: ").strip()
                    resp = requests.post(f"{SERVER}/player_guess", json={
                        "idUser"        : turn.idUser,
                        "idNPC"         : turn.idNPC,
                        "playerName"    : turn.player_name,
                        "currentScene"  : turn.current_scene,
                        "player_text"   : turn.player_text,
                        "npcText"       : ext.last_npc_response,
                        "game_started"  : gameStarted,
                        "idVoice"       : turn.voiceId,
                        "game_over"     : False
                    })
                    data = resp.json()
                    result = data.get("res")

                if result == "End":
                    print('game over')
                    return
                # -------------------------------------------------------------------
                # incorrect guess branch
                # -------------------------------------------------------------------
                while result == "False":
                    print("\n\nINCORRECT GUESS!\n\n")
                    # get player's guess for NPC's current emotion
                    turn.player_text = input("\n Respond: ").strip()
                    resp = requests.post(f"{SERVER}/player_guess", json={
                        "idUser"        : turn.idUser,
                        "idNPC"         : turn.idNPC,
                        "playerName"    : turn.player_name,
                        "currentScene"  : turn.current_scene,
                        "player_text"   : turn.player_text,
                        "npcText"       : ext.last_npc_response,
                        "game_started"  : gameStarted,
                        "idVoice"       : turn.voiceId,
                        "game_over"     : False
                    })
                    data = resp.json()
                    result = data.get("res")
        # ---------------------------------------------------------------------------
        # refused to play branch
        # ---------------------------------------------------------------------------          
        else: 
            while not agreed:
                
                print('\nDENIED!\n')
                # create prompt for when player denies NPC's game
                # returns npcs output in n
               
                requests.post(f"{SERVER}/player_not_agreed", json={
                    "idUser"        : turn.idUser,
                    "idNPC"         : turn.idNPC,
                    "playerName"    : turn.player_name,
                    "currentScene"  : turn.current_scene,
                    "player_text"   : turn.player_text,
                    "idVoice"       : turn.voiceId,
                })  
                
                # get player's response to this NPC output
                turn.player_text = input("\n Respond: ").strip()
                # Wait for semantic completion
                ext.wait_for_npc_response(timeout=30)
                
                # check again
                res = requests.post(f"{SERVER}/player_agreed_check", json={
                    "idUser"        : turn.idUser,
                    "idNPC"         : turn.idNPC,
                    "player_text"    : turn.player_text,
                    "npcText"       : ext.last_npc_response,
                    "idVoice"       : turn.voiceId,
                })
                data = res.json()  
                agreed = data.get("agreed")
                gameStarted = agreed
                ext.npc_response_ready.clear()
# -----------------------------------------------------------------------------------
# main loop
# -----------------------------------------------------------------------------------
game_start()

