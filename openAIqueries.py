from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

import re
import json
from typing import Generator, Optional
from turnContext import EmotionGameTurn

#------------------------------------------------------------------
def getResponseStream(t: EmotionGameTurn, client) -> Generator[str, None, None]:
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.85,
            top_p=0.9,
            stream=True, 
            messages=[
                {
                    "role": "system",
                    "content": t.prompt
                },
                {
                    "role": "system",
                    "content": f"""
                    CURRENT SCENE (STABLE CONTEXT – DO NOT REPEAT OR REFER TO DIRECTLY)
                    -------------
                    {t.current_scene}

                    PLAYER NAME
                    -----------
                    {t.player_name}
                    """
                }
            ],
        )

        full = []

        for chunk in response:
            delta = chunk.choices[0].delta

            if delta and delta.content:
                token = delta.content
                full.append(token)
                yield token
        return "".join(full)

    except Exception as e:
        logger.exception(f"getResponseStream failed: {e}")

#------------------------------------------------------------------
def classify_player_response_to_game_start(t : EmotionGameTurn, client):
    """
    Returns True if the player agrees to help the NPC identify their emotions.
    """
    system = """
    You are a simple yes/no classifier for a children's emotion-learning game.

    The NPC has asked the player to help identify their emotions.
    Classify whether the player AGREES to help.

    Return ONLY valid JSON:
    { "agrees_to_help": true | false }

    TRUE (agree) examples: "yes", "sure", "okay", "yeah", "of course",
        "I can help", "let's do it", "I'll try", "happy to", "absolutely",
        "why not", "I guess", "alright", "fine", "go ahead"
    FALSE (not agree) examples: "no", "not really", "I don't want to",
        "maybe later", "leave me alone", random statements not about helping

    If the player says anything that sounds like consent, cooperation,
    or willingness to participate, return true. Default to true for
    any short positive utterance. Only return false for clear refusals.
    """

    user = f"""
    The NPC just asked: "{t.last_npc_text}"

    Player replied: "{t.player_text}"

    Does the player agree to help? true or false?
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )

    logger.debug(f"PLAYER'S INPUT {t.player_text} MEANS DECIDED TO AGREE IS: {resp.choices[0].message.content}")

    result = parse_llm_json(resp.choices[0].message.content)
    return bool(result.get("agrees_to_help", False))  
#------------------------------------------------------------------
def classify_emotion_guess(t: EmotionGameTurn, client):
    system = (
        "You classify whether a child is attempting to identify an emotion.\n"
        "Map the player's input to ONE of the allowed emotions if applicable.\n"
        "If the player is not clearly guessing an emotion, return null.\n\n"
        "Allowed emotions:\n"
        "- happy\n"
        "- sad\n"
        "- angry\n"
        "- afraid\n"
        "- surprised\n"
        "- calm\n"
        "- excited\n"
        "- disgusted\n\n"
        "Return ONLY valid JSON:\n"
        "{ \"guessed_emotion\": string | null }\n"
        "Do not explain."
    )

    user = f"""
    Player input:
    \"\"\"{t.player_text}\"\"\"
    """

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.0,
    )

    result = parse_llm_json(resp.choices[0].message.content)
    return result.get("guessed_emotion")
# ------------------------------------------------------------
# OpenAI generator (returns list[str] or None)
def normalize_emotion(emotion) -> str:
    if isinstance(emotion, str):
        return emotion
    if isinstance(emotion, dict) and "emotion" in emotion:
        return emotion["emotion"]
    raise ValueError(f"Invalid emotion: {emotion!r}")
# ------------------------------------------------------------
def generate_emotion_cues(emotion: str, client) -> list[str] | None:
    # Callers (prewarm_cue_cache, get_cues_for_emotion) already normalize.
    print(f"DEBUGGING EMOTION SETTING {emotion}")

    system = (
        "You generate short descriptions of emotions for young children (ages 4-7).\n"
        "Rules:\n"
        "- Use concrete body sensations or everyday situations a young child knows\n"
        "- Use very simple words (kindergarten level)\n"
        "- No abstract or psychology words\n"
        "- Do NOT name the emotion\n"
        "- Return ONLY valid JSON\n"
    )

    user = f"""
        Generate 3 different clues for this feeling:

        Feeling: {emotion}

        Each clue must be something a 4-7 year old child can understand, like:
        1) A body feeling OR
        2) Something that happens in everyday kid life OR
        3) Something you can see someone do

        Use very simple words. Short sentences.

        Return JSON only in exactly this shape:
        {{"cues":["...","...","..."]}}
        """.strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = parse_llm_json(resp.choices[0].message.content)
        return content["cues"]

    except Exception:
        # any parse / API / schema issue -> fallback
        return None
# ------------------------------------------------------------
# Single entry point you call from build_prompt()
# ------------------------------------------------------------
# Per-emotion cue cache — avoid blocking gpt-4o-mini call on
# every turn (and the 3-5s cold-start penalty on first turn).
# Populated by prewarm_cue_cache() at server startup.
# ------------------------------------------------------------
_CUE_CACHE: dict[str, list[str]] = {}

_CUE_FALLBACK = [
    "my body feels different in a noticeable way",
    "it feels like something important is happening",
    "my face and voice change a little",
]


def prewarm_cue_cache(client) -> None:
    """Generate and cache cues for all 8 emotions at startup.

    Parallelizes the 8 independent gpt-4o-mini calls via ThreadPoolExecutor
    so startup drops from ~12s sequential to ~2s (single slowest call).
    """
    from concurrent.futures import ThreadPoolExecutor

    emotions = ["happy", "sad", "angry", "afraid", "surprised",
                "calm", "excited", "disgusted"]

    def _gen_one(emotion: str) -> None:
        try:
            _CUE_CACHE[emotion] = generate_emotion_cues(emotion, client)
            print(f"[cue-cache] pre-generated cues for '{emotion}'")
        except Exception as e:
            print(f"[cue-cache] failed for '{emotion}': {e}")
            _CUE_CACHE[emotion] = list(_CUE_FALLBACK)

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(_gen_one, emotions))

    print("[cue-cache] warmup complete")


def get_cues_for_emotion(emotion: str, client) -> list[str]:
    """
    Return 3 child-friendly cues for an emotion.
    Uses pre-generated cache; falls back to on-demand generation.
    """
    emotion = normalize_emotion(emotion)

    # Cache hit — the common case after startup warmup
    if emotion in _CUE_CACHE:
        return _CUE_CACHE[emotion]

    # Cache miss — generate on demand (rare, e.g. new emotion added)
    try:
        cues = generate_emotion_cues(emotion, client)
        if cues:
            _CUE_CACHE[emotion] = cues
            return cues
    except Exception as e:
        print(f"[CUE GEN FAILED] {emotion}: {e}")

    return list(_CUE_FALLBACK)

# ------------------------------------------------------------
def parse_llm_json(text: str) -> dict:
    """
    Robustly parse JSON returned by an LLM.
    Strips markdown fences and leading/trailing text.
    """
    if not text:
        raise ValueError("Empty LLM response")

    # Remove ```json ``` or ``` fences
    cleaned = re.sub(r"```(?:json)?", "", text).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fallback: extract first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    raise ValueError(f"Could not parse JSON from LLM output:\n{text}")