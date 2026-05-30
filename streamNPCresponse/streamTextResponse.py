import openAIqueries
import base64
import os
import re
import time
from turnContext import EmotionGameTurn
from elevenlabsQueries import tts_with_timestamps_cached, _char_alignments_to_words

CHUNK_SIZE = 32_768  # 32 KB

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
    t.word_gen = getattr(t, "word_gen", 0) + 1

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

    # Don't emit npc_audio_stop here — it kills lipsync in Unreal.
    # Old-audio cleanup is handled by t.word_gen (cancels old word
    # tasks) and Unreal's own audio queuing.

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
                return False

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
        # If Unreal is still playing previous audio, we queue behind it.
        # If there was a gap (slow OpenAI), we start at ref (now).
        sentence_start = max(ref, cumulative_end)
        audio_duration = all_ends[-1] if all_ends else 0.0
        cumulative_end = sentence_start + audio_duration

        word_timings = _char_alignments_to_words(all_chars, all_starts, all_ends)

        # Spawn a background task NOW so words start firing immediately
        # (or after previous audio, thanks to sentence_start offset).
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
                print(f"[_emit_words] background task crashed: {e}")
                import traceback
                traceback.print_exc()

        sio.start_background_task(_emit_words)

        return True

    # ----------------------------------------------------------
    # stream text + audio (closed-captioning style)
    # ----------------------------------------------------------
    _t0 = time.time()
    _first_token = False

    # --- debug: short-circuit NPC output to a few words ---
    _debug_short = os.getenv("DEBUG_SHORT_RESPONSES")
    if _debug_short:
        _debug_text = _debug_short if _debug_short.strip() else "Hello there."
        print(f"[DEBUG] Short-circuiting NPC response to: {_debug_text!r}")
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
            print(f"[TIMING] gpt-4o first token in {time.time() - _t0:.1f}s")
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

    return "".join(full_text)
