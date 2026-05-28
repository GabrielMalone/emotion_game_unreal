import openAIqueries
import base64
import re
from turnContext import EmotionGameTurn
from elevenlabsQueries import tts_with_timestamps_cached, _char_alignments_to_words

CHUNK_SIZE = 32_768  # 32 KB

def _strip_tags(text: str) -> str:
    """Remove [emotion tags] and normalize whitespace for clean text tokens."""
    text = re.sub(r'\s*\[.*?\]\s*', ' ', text)   # strip bracket tags
    text = re.sub(r'\s+', ' ', text)              # collapse newlines/tabs/multi-space → single space
    return text.strip()


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
    t.audio_ready = False
    _emit("npc_audio_stop")
    sio.sleep(0)

    # --- handshake: wait for Unreal to finish resetting its audio ---
    handshake_timeout = 3.0  # seconds
    handshake_step = 0.05
    waited = 0.0
    while not t.audio_ready and waited < handshake_timeout:
        if t.cancel_stream:
            t.streaming = False
            return ""
        sio.sleep(handshake_step)
        waited += handshake_step
    # ----------------------------------------------------------------

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
            clean_sentence = _strip_tags(sentence_buffer)

            _emit("keepalive")
            sio.sleep(0)

            _emit("npc_text_token", {"token": clean_sentence})
            sio.sleep(0.05)

            # Stream audio AND word timings together.
            # Alignment data accumulates per chunk — we emit updated
            # word timings BEFORE each audio chunk so Unreal always
            # has the latest timings before the audio plays.
            all_chars = []
            all_starts = []
            all_ends = []
            for audio_chunk, chars, starts, ends in tts_with_timestamps_cached(
                clean_sentence, t.voiceId, t.cur_npc_emotion
            ):
                if t.cancel_stream:
                    _emit("npc_audio_stop")
                    _emit("stream_cancelled")
                    t.streaming = False
                    return "".join(full_text)

                all_chars = chars
                all_starts = starts
                all_ends = ends

                # Emit latest word timings BEFORE this audio chunk
                word_timings = _char_alignments_to_words(all_chars, all_starts, all_ends)
                if word_timings:
                    _emit("npc_word_timings", {"words": word_timings})
                    sio.sleep(0)

                # Now emit the audio chunk
                _emit("npc_audio_chunk", {
                    "audio_chunk": base64.b64encode(audio_chunk).decode("utf-8"),
                })
                sio.sleep(0)

            _emit("npc_audio_done")
            sio.sleep(0)

            sentence_buffer = ""

    # ----------------------------------------------------------
    # flush remaining text
    # ----------------------------------------------------------
    if speechOn and sentence_buffer.strip():
        clean_sentence = _strip_tags(sentence_buffer)
        _emit("npc_text_token", {"token": clean_sentence})
        sio.sleep(0)

        all_chars = []
        all_starts = []
        all_ends = []
        for audio_chunk, chars, starts, ends in tts_with_timestamps_cached(
            clean_sentence, t.voiceId, t.cur_npc_emotion
        ):
            if t.cancel_stream:
                _emit("npc_audio_stop")
                _emit("stream_cancelled")
                t.streaming = False
                return "".join(full_text)

            all_chars = chars
            all_starts = starts
            all_ends = ends

            word_timings = _char_alignments_to_words(all_chars, all_starts, all_ends)
            if word_timings:
                _emit("npc_word_timings", {"words": word_timings})
                sio.sleep(0)

            _emit("npc_audio_chunk", {
                "audio_chunk": base64.b64encode(audio_chunk).decode("utf-8"),
            })
            sio.sleep(0)

        _emit("npc_audio_done")
        sio.sleep(0)
    # ----------------------------------------------------------

    t.streaming = False

    _emit("npc_stream_audio_done")
    sio.sleep(0)

    return "".join(full_text)
