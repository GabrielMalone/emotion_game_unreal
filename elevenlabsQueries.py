import os, uuid, random
import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from dotenv import load_dotenv
import hashlib
load_dotenv(".env")
AUDIO_DIR = "./tts_cache"
os.makedirs(AUDIO_DIR, exist_ok=True)

http_client = httpx.Client(timeout=240, follow_redirects=True)

_eleven = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
    httpx_client=http_client,
)

# Per-emotion VoiceSettings — TUNED FOR eleven_v3 + Charlotte
# v3 interprets [bracket tags] natively as performance cues.
# Lower stability = more emotional range (ElevenLabs docs: 0.20-0.35 is the
# "creative" sweet spot where audio tags have the most impact).
# Charlotte (XB0fDUnXU5powFXDhCwa) handles low stability cleanly without
# artifacts, so we can push emotional range further than Sarah/Amelia.
EMOTION_VOICE_SETTINGS = {
    "happy":     VoiceSettings(stability=0.22, similarity_boost=0.75, style=0.55, speed=1.10),
    "excited":   VoiceSettings(stability=0.18, similarity_boost=0.75, style=0.60, speed=1.30),
    "surprised": VoiceSettings(stability=0.20, similarity_boost=0.75, style=0.55, speed=1.20),
    "sad":       VoiceSettings(stability=0.28, similarity_boost=0.75, style=0.45, speed=0.82),
    "angry":     VoiceSettings(stability=0.18, similarity_boost=0.75, style=0.60, speed=1.35),
    "afraid":    VoiceSettings(stability=0.22, similarity_boost=0.75, style=0.50, speed=1.10),
    "disgusted": VoiceSettings(stability=0.24, similarity_boost=0.75, style=0.50, speed=0.92),
    "calm":      VoiceSettings(stability=0.32, similarity_boost=0.75, style=0.38, speed=0.88),
    "neutral":   VoiceSettings(stability=0.35, similarity_boost=0.75, style=0.32, speed=1.00),
    "worried":   VoiceSettings(stability=0.25, similarity_boost=0.75, style=0.48, speed=0.95),
}
_DEFAULT_VOICE_SETTINGS = VoiceSettings(stability=0.30, similarity_boost=0.75, style=0.35, speed=1.0)

# ==================================================================
# Audio tag vocabularies per emotion (2025/2026 ElevenLabs best practices)
#
# Key principles from ElevenLabs v3 docs:
#   - Tags affect ~4-5 words then delivery returns to baseline
#   - Place tags INLINE at emotional shift points, not just sentence starts
#   - Post-sentence reactions often sound more natural than pre-sentence
#   - Layer emotion + non-verbal: "[sad][sighs] I don't know..."
#   - Use ellipses + punctuation WITH tags for pacing/hesitation
#   - Match tags to voice character — Amelia is young, British, expressive
#   - Sparse is better: 40-60% coverage, not every sentence
# ==================================================================

# Primary emotion/delivery tags — placed at sentence start or mid-sentence
# All tags verified against ElevenLabs documentation
EMOTION_TAGS = {
    "happy":     ["[happily]", "[cheerfully]", "[warmly]", "[laughs]",
                  "[playfully]", "[brightly]"],
    "excited":   ["[excited]", "[eagerly]", "[enthusiastically]",
                  "[energetically]", "[excitedly]"],
    "surprised": ["[surprised]", "[gasps]", "[astonished]", "[incredulously]",
                  "[shocked]"],
    "sad":       ["[sadly]", "[sorrowful]", "[quietly]", "[sighs]",
                  "[melancholy]", "[resigned]"],
    "angry":     ["[angrily]", "[frustrated]", "[harsh]", "[indignant]",
                  "[irritated]", "[annoyed]"],
    "afraid":    ["[nervously]", "[whispering]", "[fearfully]", "[trembling]",
                  "[timidly]", "[uncertain]"],
    "disgusted": ["[disgusted]", "[appalled]", "[dismissive]",
                  "[sarcastic]", "[disdain]"],
    "calm":      ["[calmly]", "[gently]", "[softly]", "[warm]",
                  "[soothingly]", "[peacefully]"],
    "neutral":   ["[thoughtfully]", "[matter-of-fact]", "[conversationally]",
                  "[reflectively]"],
    "worried":   ["[worried]", "[hesitant]", "[nervous]", "[uncertain]",
                  "[apprehensively]", "[troubled]"],
}

# Non-verbal reactions & human sounds — placed MID-SENTENCE or POST-SENTENCE
# for natural emotional beats (sighs, gulps, laughs, etc.)
# Used at ~15-25% probability on any given sentence
_REACTION_TAGS = {
    "happy":     ["[laughs]", "[chuckles]", "[giggles]", "[light chuckle]"],
    "excited":   ["[laughs]", "[gasps]", "[exhales sharply]", "[laughing]"],
    "surprised": ["[gasps]", "[gulps]", "[sharp inhale]", "[exhales]"],
    "sad":       ["[sighs]", "[sniffles]", "[quiet exhale]", "[sigh]",
                  "[voice catches]"],
    "angry":     ["[snorts]", "[growls]", "[huffs]", "[grumbles]"],
    "afraid":    ["[gulps]", "[whispers]", "[stammers]", "[trembling]",
                  "[shaky breath]"],
    "disgusted": ["[shudders]", "[sighs]", "[groans]", "[scoffs]"],
    "calm":      ["[sighs contentedly]", "[exhales]", "[gentle exhale]",
                  "[soft chuckle]"],
    "neutral":   ["[clears throat]", "[pause]", "[slight pause]"],
    "worried":   ["[sighs]", "[nervous laugh]", "[gulps]", "[stammers]",
                  "[hesitates]", "[shaky exhale]"],
}

# Pacing/hesitation tags — used at natural break points
# Placed BEFORE a sentence or MID-SENTENCE at hesitation points
_PACING_TAGS = {
    "sad":       ["[hesitates]", "[pause]", "[quietly]"],
    "afraid":    ["[stammers]", "[hesitates]", "[pause]", "[trembling]"],
    "worried":   ["[hesitates]", "[pause]", "[stammers]", "[uncertain]"],
    "surprised": ["[pause]", "[stammers]", "[incredulously]"],
    "disgusted": ["[pause]", "[scoffs]"],
    "neutral":   ["[pause]", "[thoughtfully]"],
    # happy, excited, angry, calm typically don't need pacing tags
}

# Cache helpers
def tts_cache_key(text, voice_id, emotion):
    raw = f"{voice_id}|{emotion}|{text.strip()}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def saveAudio(audio):
    audio = b"".join(audio)
    audio_id = str(uuid.uuid4())
    path = f"{AUDIO_DIR}/{audio_id}.mp3"
    with open(path, "wb") as f:
        f.write(audio)
    return {"audio_id": audio_id}, 200

def tts_cached(text, voice_id, emotion):
    key = tts_cache_key(text, voice_id, emotion)
    path = f"{AUDIO_DIR}/{key}.mp3"
    if os.path.exists(path):
        print("USING CACHE!")
        with open(path, "rb") as f:
            while True:
                chunk = f.read(32_768)
                if not chunk:
                    break
                yield chunk
        return
    for chunk in tts(text, voice_id, emotion):
        yield chunk

def speech_to_text(wav_path: str) -> str:
    pass

# Main TTS function
def tts(text, voice_id, emotion):
    print("\nTTS DEBUG:\n", voice_id)
    voice_settings = EMOTION_VOICE_SETTINGS.get(emotion, _DEFAULT_VOICE_SETTINGS)
    tagged_text = _apply_audio_tags(text, emotion)
    print(f"voiceID: {voice_id}  emotion: {emotion}")
    print(f"text: {tagged_text}")
    audio_stream = _eleven.text_to_speech.convert(
        voice_id=voice_id,
        text=tagged_text,
        model_id="eleven_v3",  # native [bracket tag] support — tags control delivery, not spoken
        voice_settings=voice_settings,
    )
    for chunk in audio_stream:
        if chunk:
            yield chunk

def _apply_audio_tags(text: str, emotion: str) -> str:
    """Apply ElevenLabs v3 audio tags using 2025/2026 best practices.

    Strategy (per ElevenLabs docs):
      - Each tag affects ~4-5 words, then delivery returns to baseline.
        This means we CAN use multiple tags per sentence at emotional
        shift points — they don't stack unnaturally.
      - Prepend tags for sentence-level emotional framing.
      - Postpend non-verbal reactions (sighs, laughs) for natural beats.
      - Mid-sentence tags at hesitation / emotional-shift points.
      - Sparse coverage: 50-65% of sentences, not every one.
      - Layer emotion + non-verbal: "[sad][sighs] I don't know..."
      - Match tone to Amelia: young, enthusiastic — avoid harsh/aggressive combos.
    """
    emotion_tags = EMOTION_TAGS.get(emotion, ["[thoughtfully]"])
    reaction_tags = _REACTION_TAGS.get(emotion, [])
    pacing_tags = _PACING_TAGS.get(emotion, [])

    # --- split into sentences -------------------------------------------------
    sentences = []
    current = ""
    for ch in text:
        current += ch
        if ch in ".?!":
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    if not sentences:
        return text

    # --- tag each sentence ----------------------------------------------------
    tagged_parts = []
    for i, sentence in enumerate(sentences):
        # ---- determine coverage for this sentence ----
        # First sentence always gets emotional framing.
        # Others get 50-65% coverage for natural variation.
        if i == 0:
            tag_it = True
        else:
            tag_it = random.random() < 0.55  # ~55% coverage

        if not tag_it:
            tagged_parts.append(sentence)
            continue

        # ---- build tags for this sentence ----
        chosen_tags = []

        # Emotional direction tag (prepend — frames the sentence)
        etag = random.choice(emotion_tags)
        chosen_tags.append(etag)

        # Non-verbal reaction (prepend or postpend based on type)
        if reaction_tags and random.random() < 0.20:
            rtag = random.choice(reaction_tags)
            # Reactions like [laughs], [sighs], [gasps] work well AFTER
            # the sentence. Others like [whispers], [gulps] work before.
            post_reactions = {"[laughs]", "[chuckles]", "[giggles]",
                              "[sighs]", "[sigh]", "[sniffles]",
                              "[gasps]", "[groans]", "[scoffs]",
                              "[grumbles]", "[huffs]", "[shudders]",
                              "[snorts]", "[growls]", "[exhales]",
                              "[light chuckle]", "[soft chuckle]",
                              "[quiet exhale]", "[gentle exhale]",
                              "[nervous laugh]", "[shaky exhale]",
                              "[exhales sharply]", "[sharp inhale]",
                              "[shaky breath]", "[voice catches]",
                              "[laughing]", "[sighs contentedly]"}
            if rtag.strip("[]") in {t.strip("[]") for t in post_reactions}:
                chosen_tags.append(("POST", rtag))
            else:
                chosen_tags.append(rtag)

        # Pacing/hesitation tag — randomly inserted for hesitant emotions
        if pacing_tags and random.random() < 0.15:
            ptag = random.choice(pacing_tags)
            # [hesitates], [stammers], [pause] work best mid-sentence
            # Place them between words in the first half of the sentence
            words = sentence.split()
            if len(words) >= 4:
                insert_at = random.randint(1, min(3, len(words) - 1))
                words.insert(insert_at, ptag)
                sentence = " ".join(words)
                # Don't add to chosen_tags since we baked it inline
            else:
                chosen_tags.append(ptag)

        # ---- assemble: prepend tags + sentence + postpend tags ----
        pre_tags = [t for t in chosen_tags if not isinstance(t, tuple)]
        post_tags = [t[1] for t in chosen_tags if isinstance(t, tuple)]

        prefix = "".join(pre_tags) + " " if pre_tags else ""
        suffix = " " + "".join(post_tags) if post_tags else ""

        tagged_parts.append(f"{prefix}{sentence}{suffix}")

    return " ".join(tagged_parts)
