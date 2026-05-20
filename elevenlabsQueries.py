import os, uuid, random
import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.types import VoiceSettings
from dotenv import load_dotenv
import hashlib
from streamingMP3Player import StreamingMP3Player

load_dotenv(".env")
AUDIO_DIR = "./tts_cache"
os.makedirs(AUDIO_DIR, exist_ok=True)

LOCAL_PLAYBACK = os.getenv("TTS_LOCAL_PLAYBACK", "0") == "1"
_active_players = []

def _new_player_if_enabled():
    if not LOCAL_PLAYBACK:
        return None
    p = StreamingMP3Player()
    _active_players.append(p)
    p.on_drain = lambda p=p: _active_players.remove(p) if p in _active_players else None
    return p

PROXY_URL = os.getenv("SOCKS_PROXY", "socks5://127.0.0.1:1080")
http_client = httpx.Client(proxy=PROXY_URL, timeout=240, follow_redirects=True)

_eleven = ElevenLabs(
    api_key=os.getenv("ELEVENLABS_API_KEY"),
    httpx_client=http_client,
)

# Per-emotion VoiceSettings
# stability: 0.35-0.50 keeps expressiveness without accent drift
# style:     0.25-0.35 adds character without amplifying vocal artifacts
EMOTION_VOICE_SETTINGS = {
    "happy":     VoiceSettings(stability=0.38, similarity_boost=0.75, style=0.30, speed=1.05, use_speaker_boost=True),
    "excited":   VoiceSettings(stability=0.35, similarity_boost=0.75, style=0.35, speed=1.15, use_speaker_boost=True),
    "surprised": VoiceSettings(stability=0.35, similarity_boost=0.75, style=0.30, speed=1.10, use_speaker_boost=True),
    "sad":       VoiceSettings(stability=0.42, similarity_boost=0.75, style=0.25, speed=0.88, use_speaker_boost=True),
    "angry":     VoiceSettings(stability=0.35, similarity_boost=0.75, style=0.35, speed=1.20, use_speaker_boost=True),
    "afraid":    VoiceSettings(stability=0.35, similarity_boost=0.75, style=0.28, speed=1.05, use_speaker_boost=True),
    "disgusted": VoiceSettings(stability=0.38, similarity_boost=0.75, style=0.30, speed=0.95, use_speaker_boost=True),
    "calm":      VoiceSettings(stability=0.45, similarity_boost=0.75, style=0.25, speed=0.92, use_speaker_boost=True),
    "neutral":   VoiceSettings(stability=0.48, similarity_boost=0.75, style=0.20, speed=1.00, use_speaker_boost=True),
    "worried":   VoiceSettings(stability=0.38, similarity_boost=0.75, style=0.28, speed=0.95, use_speaker_boost=True),
}
_DEFAULT_VOICE_SETTINGS = VoiceSettings(stability=0.40, similarity_boost=0.75, style=0.25, speed=1.0, use_speaker_boost=True)

# Audio tag vocabularies per emotion
# Use emotional adjectives only -- delivery-description tags like
# [voice breaking], [trembling], [shakily] cause voice instability.
EMOTION_TAGS = {
    "happy":     ["[happily]", "[laughs]", "[warmly]"],
    "excited":   ["[excitedly]", "[excited]", "[eagerly]"],
    "surprised": ["[surprised]", "[astonished]"],
    "sad":       ["[sadly]", "[sighs]", "[quietly]"],
    "angry":     ["[angrily]", "[frustrated]", "[sharply]"],
    "afraid":    ["[nervously]", "[fearfully]", "[whispers]"],
    "disgusted": ["[disgusted]", "[queasily]"],
    "calm":      ["[calmly]", "[gently]", "[soothingly]"],
    "neutral":   ["[thoughtfully]"],
    "worried":   ["[worriedly]", "[uncertainly]", "[anxiously]"],
}
# Non-verbal reactions -- used sparingly (10% chance per sentence)
_REACTION_TAGS = {
    "happy":     ["[laughs]", "[chuckles]"],
    "excited":   ["[laughs]", "[gasps]"],
    "surprised": ["[gasps]"],
    "sad":       ["[sighs]", "[sniffles]"],
    "angry":     ["[snorts]"],
    "afraid":    ["[gulps]", "[whispers]"],
    "disgusted": ["[shudders]", "[sighs]"],
    "calm":      ["[sighs contentedly]", "[exhales]"],
    "neutral":   ["[clears throat]"],
    "worried":   ["[sighs]", "[nervous laugh]", "[gulps]"],
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
        model_id="eleven_v3",
        voice_settings=voice_settings,
    )
    for chunk in audio_stream:
        if chunk:
            yield chunk

def _apply_audio_tags(text: str, emotion: str) -> str:
    """Sprinkle emotion-appropriate audio tags through the text.

    Best practices from ElevenLabs docs:
    - One tag per sentence is enough (too many = forced/unnatural)
    - Match tags to the voice's character (Emory = warm, not aggressive)
    - First sentence gets the strongest tag, rest get lighter touches
    - Non-verbal reactions (sighs, laughs) used sparingly (~15%)
    """
    tags = EMOTION_TAGS.get(emotion, ["[thoughtfully]"])
    if not tags:
        return text

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

    tagged_parts = []
    for i, sentence in enumerate(sentences):
        if i == 0:
            # First sentence: single strong tag (not double — double
            # tags can cause the voice to "break" between registers)
            tag = random.choice(tags)
            tagged_parts.append(f"{tag} {sentence}")
        else:
            # Subsequent sentences: lighter tagging
            if random.random() < 0.8:
                # 80% of sentences get a tag — but a milder one
                tag = random.choice(tags)
                tagged_parts.append(f"{tag} {sentence}")
            else:
                # 20% get no tag — lets the voice settle naturally
                tagged_parts.append(sentence)

    return " ".join(tagged_parts)
