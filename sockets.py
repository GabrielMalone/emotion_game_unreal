from flask_socketio import SocketIO, join_room
from UnrealPhase1 import active_turns, start_game, advance_game, currentScene, idUser, voiceId
from emotionGameQueries import get_active_emotion, get_num_correct
#------------------------------------------------------------------
from db import connect
#------------------------------------------------------------------
sio = SocketIO(cors_allowed_origins="*")
#------------------------------------------------------------------
def init_socket_events(app):

    sio.init_app(app)
    #--------------------------------------------------------------
    # testing 
    @sio.on("connect")
    def on_connect():
        print("player connected")
        # Immediate test - no room routing, no conditions
        sio.emit("npc_audio_chunk", {"immediate": "test"})
        sio.emit("test_connect", {"msg": "connected"})

    @sio.on("ping")
    def ping(data=None):
        sio.emit("pong", "HELLO_FROM_FLASK")
    
    @sio.on("test_audio")
    def test_audio(data=None):
        print("Test audio requested - sending multiple test events")
        # Test 1: Same format as working text token
        sio.emit("npc_text_token", {"token": "TEST_TOKEN"})
        # Test 2: Similar name pattern  
        sio.emit("npc_test_chunk", {"test": "test2"})
        # Test 3: The problematic event
        sio.emit("npc_audio_chunk", {"test": "test3"})
        # Test 4: Without npc prefix
        sio.emit("audio_chunk", {"test": "test4"})
        # Test 5: Different format
        sio.emit("npcAudioChunk", {"test": "test5"})

    @sio.on("get_cur_emotion")
    def getCurEmotion(data=None):
        db = connect()
        cursor = db.cursor()
        cursor.execute("""
            SELECT e.emotion
            FROM emotion_guess_game g
            JOIN emotion e ON e.idEmotion = g.idEmotion
            WHERE g.idUser = 1
                AND g.idNPC = 1
                AND g.active = 1
            LIMIT 1;
        """)
        emotion = cursor.fetchone()
        print('current emotion from backend', emotion)
        sio.emit("send_cur_emotion", emotion)

    
    #--------------------------------------------------------------
    # can update this in the future to get 
    # the player & scene data from unreal
    @sio.on("disconnect")
    def on_disconnect():
        """Unreal closed the socket — cancel any in-flight stream so the
        backend doesn't crash trying to emit to a dead connection."""
        turn = active_turns.get(idUser)
        if turn is not None:
            turn.cancel_stream = True
        print(f"[disconnect] user {idUser} disconnected, cancel_stream set")

    @sio.on("register_user")
    def register_user(data=None):
        player_name = None
        if data and data.get("player_name", "").strip():
            player_name = data["player_name"].strip()
        join_room(f"user:{idUser}")   # THIS WAS MISSING
        start_game(sio=sio, player_name=player_name)
    #--------------------------------------------------------------
    # from unreal socket emit event
    # get the player's input
    @sio.on("player_input")
    def on_player_input(data):
        if not data:
            print("[player_input] received empty data, ignoring")
            return
        turn = active_turns[idUser]
        # Kill any in-flight TTS immediately — player is interacting,
        # don't make them wait for old audio to finish.
        turn.cancel_stream = True
        sio.emit("npc_audio_stop", {}, room=f"user:{turn.idUser}")
        print("[player_input] cancel_stream set, npc_audio_stop emitted")

        advance_game(turn, data.get("player_text", ""), data.get("last_npc_text", ""), sio=sio)
        #--------------------------------------------------------------
    # ---------------------------------------------------------------
    # from unreal socket emit event
    # Player walked away from (or returned to) the NPC.
    # On walk-away: cancel any in-flight OpenAI/TTS stream.
    # On return:    process the player's text through advance_game
    #               so the NPC recognizes they came back.
    @sio.on("player_stepped_away")
    def on_player_stepped_away(data=None):
        turn = active_turns.get(idUser)
        if turn is None:
            return
        # Cancel any in-flight stream *first* (sets cancel_stream so
        # the streamResponse loop aborts at its next token/chunk).
        turn.cancel_stream = True
        print(f"[player_stepped_away] cancel flag set for user {idUser}")

        # If Unreal included player text, this is a *return* — process
        # it through the normal game loop so the NPC responds.
        if data and data.get("player_text", "").strip():
            advance_game(
                turn,
                data.get("player_text", ""),
                data.get("last_npc_text", ""),
                sio=sio,
            )
