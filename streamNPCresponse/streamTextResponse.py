import logging
import openAIqueries
import base64
import os
import re
import time
import threading
import queue
from turnContext import EmotionGameTurn
from elevenlabsQueries import tts_with_timestamps_cached, _char_alignments_to_words

logger = logging.getLogger(__name__)

CHUNK_SIZE = 32_768  # 32 KB

def _strip_tags(text: str) -> str:
    """Remove [emotion tags] and normalize whitespace for clean text tokens."""
    text = re.sub(r'\s*\[.*?\]\s*', ' ', text)   # strip bracket tags
    text = re.sub(r'\s+', ' ', text)              # collapse newlines/tabs/multi-space -> single space
    return text.strip()


def streamResponse(t: EmotionGameTurn, client, sio) -> str:
    """Stream NPC response with parallel TTS pipeline.

    GPT-4o token consumption and ElevenLabs TTS synthesis run in
    parallel: as soon as a sentence is complete, it is pushed to a
    queue for the TTS worker thread.  The GPT loop continues
    immediately so sentence N+1 is being generated while sentence N
    is being synthesized.  This overlaps the two most expensive
    operations in the pipeline (~1-3s saved per multi-sentence turn).
    """
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

    # ------------------------------------------------------------------
    # Producer-consumer: GPT loop → sentence_queue → TTS worker thread
    # ------------------------------------------------------------------
    sentence_queue = queue.Queue()
    cumulative_end = 0.0
    worker_error = [None]  # mutable container for exception propagation

    def _tts_worker():
        """Background thread: pull sentences from queue, run TTS, emit audio.

        Runs sequentially so sentence ordering is guaranteed.  While
        this thread is synthesizing sentence N, the GPT loop is already
        generating tokens for sentence N+1.
        """
        nonlocal cumulative_end
        try:
            while True:
                item = sentence_queue.get()
                if item is None:  # sentinel — all sentences queued
                    break
                if t.cancel_stream:
                    break

                clean_sentence = item

                _emit("keepalive")
                sio.sleep(0)

                _emit("npc_text_token", {"token": clean_sentence})
                sio.sleep(0.05)

                ref = time.time()
                all_chars = []
                all_starts = []
                all_ends = []
                for audio_chunk, chars, starts, ends in tts_with_timestamps_cached(
                    clean_sentence, t.voiceId, t.cur_npc_emotion
                ):
                    if t.cancel_stream:
                        _emit("stream_cancelled")
                        t.streaming = False
                        return

                    all_chars = chars
                    all_starts = starts
                    all_ends = ends

                    _emit("npc_audio_chunk", {
                        "audio_chunk": base64.b64encode(audio_chunk).decode("utf-8"),
                    })
                    sio.sleep(0)

                _emit("npc_audio_done")
                sio.sleep(0)

                # This sentence's audio will start playing at:
                #   max(ref, cumulative_end)
                sentence_start = max(ref, cumulative_end)
                audio_duration = all_ends[-1] if all_ends else 0.0
                cumulative_end = sentence_start + audio_duration

                word_timings = _char_alignments_to_words(all_chars, all_starts, all_ends)

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

        except Exception as e:
            worker_error[0] = e
            logger.error(f"[_tts_worker] crashed: {e}", exc_info=True)
            t.cancel_stream = True

    # Start TTS worker thread — runs in parallel with GPT token loop
    worker = threading.Thread(target=_tts_worker, daemon=True)
    worker.start()

    # ----------------------------------------------------------
    # GPT token loop — pushes sentences to queue, continues immediately
    # ----------------------------------------------------------
    _t0 = time.time()
    _first_token = False

    # --- debug: short-circuit NPC output to a few words ---
    _debug_short = os.getenv("DEBUG_SHORT_RESPONSES")
    if _debug_short:
        _debug_text = _debug_short if _debug_short.strip() else "Hello there."
        logger.debug(f"Short-circuiting NPC response to: {_debug_text!r}")
        def _debug_gen(text: str):
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
            sentence_queue.put(None)  # wake worker so it can exit
            worker.join(timeout=5)
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
            sentence_queue.put(clean_sentence)
            sentence_buffer = ""

    # ----------------------------------------------------------
    # flush remaining text
    # ----------------------------------------------------------
    if speechOn and sentence_buffer.strip():
        clean_sentence = _strip_tags(sentence_buffer)
        sentence_queue.put(clean_sentence)
    # ----------------------------------------------------------

    # Signal worker that all sentences are queued, then wait for it
    sentence_queue.put(None)
    worker.join(timeout=60)

    if worker_error[0]:
        logger.error(f"TTS worker failed: {worker_error[0]}")

    t.streaming = False

    _emit("npc_stream_audio_done")
    sio.sleep(0)

    return "".join(full_text)
