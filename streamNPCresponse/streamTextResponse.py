import openAIqueries
import base64
import re
from turnContext import EmotionGameTurn
from elevenlabsQueries import tts_cached

CHUNK_SIZE = 32_768  # 32 KB

def _strip_tags(text: str) -> str:
    """Remove [emotion tags] like [happily], [sighs], [laughs] etc."""
    return re.sub(r'\s*\[.*?\]\s*', ' ', text).strip()


def streamResponse(t: EmotionGameTurn, client, sio) -> str:
    full_text = []
    sentence_buffer = ""
    SENTENCE_END = {".", "?", "!"}
    speechOn = True
    # Clear any stale cancel flag from a previous walk-away that
    # didn't coincide with an active stream.
    t.cancel_stream = False
    t.streaming = True

    # ------------------------------------------------------------------
    # Safe emit helper
    # ------------------------------------------------------------------
    def _emit(event: str, data: dict | None = None) -> bool:
        if data is None:
            data = {}
        try:
            sio.emit(event, data, room=f"user:{t.idUser}")
            return True
        except Exception:
            t.cancel_stream = True
            return False

    # Tell Unreal to flush any queued audio from a previous stream
    # BEFORE we start emitting new chunks. This prevents old TTS from
    # playing over new dialogue when the player skips ahead.
    _emit("npc_audio_stop")
    sio.sleep(0)

    # ----------------------------------------------------------
    # stream text + audio (closed-captioning style)
    # ----------------------------------------------------------
    for token in openAIqueries.getResponseStream(t, client):
        # --- player walked away or socket died? abort immediately ---
        if t.cancel_stream:
            _emit("npc_audio_stop")
            _emit("stream_cancelled")
            t.streaming = False
            return "".join(full_text)

        full_text.append(token)
        sentence_buffer += token
        sio.sleep(0)

        if (
            speechOn
            and sentence_buffer.strip()
            and sentence_buffer.strip()[-1] in SENTENCE_END
        ):
            # Strip emotion tags so Unreal gets clean text for CC display
            # AND so ElevenLabs doesn't read stage directions aloud
            clean_sentence = _strip_tags(sentence_buffer)

            # Send keepalive before audio processing
            _emit("keepalive")
            sio.sleep(0)

            # Emit the clean text FIRST so it appears alongside the
            # audio chunks that follow (closed-captioning sync)
            _emit("npc_text_token", {"token": clean_sentence})
            sio.sleep(0)

            audio_buf = b""
            for audio_chunk in tts_cached(
                clean_sentence, t.voiceId, t.cur_npc_emotion
            ):
                if t.cancel_stream:
                    _emit("npc_audio_stop")
                    _emit("stream_cancelled")
                    t.streaming = False
                    return "".join(full_text)

                audio_buf += audio_chunk
                while len(audio_buf) >= CHUNK_SIZE:
                    print("SENDING AUDIO EMIT (sentence)")
                    _emit("npc_audio_chunk", {
                        "audio_chunk": base64.b64encode(audio_buf[:CHUNK_SIZE]).decode("utf-8"),
                    })
                    audio_buf = audio_buf[CHUNK_SIZE:]
                    sio.sleep(0)
            if audio_buf:
                print("SENDING AUDIO EMIT (sentence tail)")
                _emit("npc_audio_chunk", {
                    "audio_chunk": base64.b64encode(audio_buf).decode("utf-8"),
                })
                sio.sleep(0)

            sentence_buffer = ""

    # ----------------------------------------------------------
    # flush remaining text
    # ----------------------------------------------------------
    if speechOn and sentence_buffer.strip():
        clean_sentence = _strip_tags(sentence_buffer)
        _emit("npc_text_token", {"token": clean_sentence})
        sio.sleep(0)

        audio_buf = b""
        for audio_chunk in tts_cached(
            clean_sentence, t.voiceId, t.cur_npc_emotion
        ):
            if t.cancel_stream:
                _emit("npc_audio_stop")
                _emit("stream_cancelled")
                t.streaming = False
                return "".join(full_text)

            audio_buf += audio_chunk
            while len(audio_buf) >= CHUNK_SIZE:
                print("SENDING AUDIO EMIT (flush)")
                _emit("npc_audio_chunk", {
                    "audio_chunk": base64.b64encode(audio_buf[:CHUNK_SIZE]).decode("utf-8"),
                })
                audio_buf = audio_buf[CHUNK_SIZE:]
                sio.sleep(0)
        if audio_buf:
            print("SENDING AUDIO EMIT (flush tail)")
            _emit("npc_audio_chunk", {
                "audio_chunk": base64.b64encode(audio_buf).decode("utf-8"),
            })
            sio.sleep(0)
    # ----------------------------------------------------------

    t.streaming = False
    return "".join(full_text)




