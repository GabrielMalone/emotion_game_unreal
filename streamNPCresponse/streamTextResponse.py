import logging
import openAIqueries
import base64
import os
import re
import time
from turnContext import EmotionGameTurn
from elevenlabsQueries import tts_with_timestamps_cached, _char_alignments_to_words, VOICE_ENABLED

logger = logging.getLogger(__name__)

CHUNK_SIZE = 32_768  # 32 KB

# ------------------------------------------------------------------
# Debug voice: when VOICE_ENABLED is False, stream arnold.mp3 as
# placeholder audio.  Emitted once per NPC response (not per sentence)
# to keep debugging fast.  Offset advances through the file so each
# NPC turn sounds different.
# ------------------------------------------------------------------
_DEBUG_AUDIO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "arnold.mp3")
_DEBUG_AUDIO_DATA: bytes | None = None
_DEBUG_AUDIO_OFFSET: int = 0
_DEBUG_AUDIO_CHUNKS_PER_RESPONSE = 1  # 1 × 32KB ≈ 32KB ≈ 2 sec per NPC response

def _load_debug_audio() -> bytes:
    """Lazy-load arnold.mp3 into memory (cached after first call)."""
    global _DEBUG_AUDIO_DATA
    if _DEBUG_AUDIO_DATA is None:
        try:
            with open(_DEBUG_AUDIO_FILE, "rb") as f:
                _DEBUG_AUDIO_DATA = f.read()
            logger.info(f"[debug-audio] loaded {_DEBUG_AUDIO_FILE} ({len(_DEBUG_AUDIO_DATA)} bytes)")
        except FileNotFoundError:
            logger.warning(f"[debug-audio] {_DEBUG_AUDIO_FILE} not found — falling back to silent words")
            _DEBUG_AUDIO_DATA = b""
    return _DEBUG_AUDIO_DATA


def _emit_debug_audio(sio, _emit, t, chunk_count: int = 2) -> None:
    """Emit a few chunks of arnold.mp3 always from the start (safe for every turn)."""
    audio = _load_debug_audio()
    if not audio:
        return
    for i in range(chunk_count):
        if t.cancel_stream:
            break
        start = i * CHUNK_SIZE
        chunk = audio[start : start + CHUNK_SIZE]
        if not chunk:
            break
        _emit("npc_audio_chunk", {"audio_chunk": base64.b64encode(chunk).decode("utf-8")})
        sio.sleep(0)

def _strip_tags(text: str) -> str:
    """Remove [emotion tags] and normalize whitespace for clean text tokens."""
    text = re.sub(r'\s*\[.*?\]\s*', ' ', text)   # strip bracket tags
    text = re.sub(r'\s+', ' ', text)              # collapse newlines/tabs/multi-space -> single space
    return text.strip()


def streamResponse(t: EmotionGameTurn, client, sio) -> str:
    full_text = []
    sentence_buffer = ""
    SENTENCE_END = {".", "?", "!"}
    speechOn = True

    # Clear any stale cancel flag from a previous walk-away.
    t.cancel_stream = False
    t.streaming = True
    # Always bump word_gen so old _emit_words tasks from any
    # previous stream (natural or interrupted) are cancelled.
    t.word_gen += 1

    # ------------------------------------------------------------------
    # Safe emit helper — logs errors without destroying the stream
    # ------------------------------------------------------------------
    def _emit(event: str, data: dict | None = None) -> bool:
        if data is None:
            data = {}
        try:
            sio.emit(event, data, room=f"user:{t.idUser}")
            return True
        except Exception as e:
            logger.warning(f"_emit failed for event '{event}': {e}")
            t.cancel_stream = True
            return False

    # When the last queued audio chunk will finish playing in Unreal.
    # Each sentence's word task uses max(ref, cumulative_end) so its
    # first word doesn't fire until previous audio finishes.
    cumulative_end = 0.0
    # ----------------------------------------------------------------

    def _process_sentence(clean_sentence: str):
        nonlocal cumulative_end

        _emit("keepalive")
        sio.sleep(0)

        _emit("npc_text_token", {"token": clean_sentence})
        sio.sleep(0.05)

        all_chars = []
        all_starts = []
        all_ends = []
        tts_ok = True

        try:
            ref = time.time()
            for audio_chunk, chars, starts, ends in tts_with_timestamps_cached(
                clean_sentence, t.voiceId, t.cur_npc_emotion
            ):
                if t.cancel_stream:
                    _emit("stream_cancelled")
                    t.streaming = False
                    return False

                all_chars = chars
                all_starts = starts
                all_ends = ends

                if audio_chunk:
                    _emit("npc_audio_chunk", {
                        "audio_chunk": base64.b64encode(audio_chunk).decode("utf-8"),
                    })
                    sio.sleep(0)
        except Exception as e:
            logger.warning(f"TTS failed: {e} — falling back to server-timed word display")
            tts_ok = False
            ref = time.time()

        sentence_start = max(ref, cumulative_end)
        audio_duration = all_ends[-1] if all_ends else 0.0
        cumulative_end = sentence_start + audio_duration

        word_timings = _char_alignments_to_words(all_chars, all_starts, all_ends)

        # --- Real audio + aligned word timings ---
        if tts_ok and word_timings:
            def _emit_words():
                try:
                    gen = t.word_gen
                    for w in word_timings:
                        if t.word_gen != gen or t.cancel_stream:
                            break
                        delay = (sentence_start + w["start"]) - time.time()
                        if delay > 0:
                            sio.sleep(delay)
                        if t.word_gen != gen or t.cancel_stream:
                            break
                        if not _emit("show_word", {"word": w["word"]}):
                            break
                except Exception as e:
                    logger.error(f"[_emit_words] background task crashed: {e}", exc_info=True)

            sio.start_background_task(_emit_words)

            _emit("npc_audio_done")

        # --- Debug voice: words only, no delay (audio was emitted once at response start) ---
        else:
            raw_words = clean_sentence.split()
            for w in raw_words:
                if t.cancel_stream:
                    break
                if not _emit("show_word", {"word": w}):
                    break
                sio.sleep(0.05)  # 50 ms per word (debugging speed)
            _emit("npc_audio_done")

        return True

    # ----------------------------------------------------------
    # Debug voice: fire placeholder audio once per NPC response.
    # Offset advances so each turn sounds different.
    # ----------------------------------------------------------
    if not VOICE_ENABLED:
        _emit_debug_audio(sio, _emit, t, chunk_count=_DEBUG_AUDIO_CHUNKS_PER_RESPONSE)

    # ----------------------------------------------------------
    # stream text + audio (closed-captioning style)
    # ----------------------------------------------------------
    _t0 = time.time()
    _first_token = False

    # --- debug: short-circuit NPC output to a few words ---
    _debug_short = os.getenv("DEBUG_SHORT_RESPONSES")
    if _debug_short:
        _debug_text = _debug_short if _debug_short.strip() else "Hello there."
        logger.debug(f"Short-circuiting NPC response to: {_debug_text!r}")
        # wrap in a generator to mimic OpenAI streaming
        def _debug_gen(text: str):
            # yield sentence-ending punctuation immediately so
            # the sentence-processing loop fires without waiting
            for ch in text:
                yield ch
        _stream = _debug_gen(_debug_text)
    else:
        _stream = openAIqueries.getResponseStream(t, client)

    for token in _stream:
        if not _first_token:
            _first_token = True
            logger.info(f"gpt-4o first token in {time.time() - _t0:.1f}s")
        # --- player walked away or socket died? abort immediately ---
        if t.cancel_stream:
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
            if not _process_sentence(clean_sentence):
                return "".join(full_text)
            sentence_buffer = ""

    # ----------------------------------------------------------
    # flush remaining text
    # ----------------------------------------------------------
    if speechOn and sentence_buffer.strip():
        clean_sentence = _strip_tags(sentence_buffer)
        _process_sentence(clean_sentence)
    # ----------------------------------------------------------

    t.streaming = False

    _emit("npc_stream_audio_done")
    sio.sleep(0)

    # When voice is disabled, the caller emits npc_responded immediately
    # after we return.  Yield so Unreal has time to process the last
    # npc_text_token/show_word events before npc_responded overwrites.
    if not VOICE_ENABLED:
        sio.sleep(0.5)

    return "".join(full_text)
