from __future__ import annotations

from emotionGameQueries import *
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
        print("ERROR:", e)

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

    print(f"\n PLAYER'S INPUT {t.player_text} MEANS DECIDED TO AGREE IS: {resp.choices[0].message.content}")

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
        "- surpised\n"
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

    emotion = normalize_emotion(emotion)
    print(f"DEBUGGING EMOTION SETTING {emotion}")

    system = (
        "You generate short,descriptions of emotions.\n"
        "Rules:\n"
        "- Use concrete body sensations or everyday situations\n"
        "- No abstract psychology words\n"
        "- Do NOT name the emotion\n"
        "- Return ONLY valid JSON\n"
    )

    user = f"""
        Generate 3 different clues for this emotion:

        Emotion: {emotion}

        Each clue must be:
        1) A body feeling OR
        2) A familiar kid experience OR
        3) A visible behavior

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
def get_cues_for_emotion(emotion: str, client) -> list[str]:
    """
    Always returns 3 child-friendly cues generated by OpenAI.
    Falls back to safe generic cues ONLY if generation fails.
    """

    try:
        cues = generate_emotion_cues(emotion, client)
        return cues

    except Exception as e:
        print(f"[CUE GEN FAILED] {emotion}: {e}")

    # absolute last-resort fallback (never emotion-specific)
    return [
        "my body feels different in a noticeable way",
        "it feels like something important is happening",
        "my face and voice change a little"
    ]

# ------------------------------------------------------------
def match_choice_query(client):
    """
    Match a player's storylet choice to determine outcomes.
    Currently a stub -- implement based on game design requirements.

    Expected request JSON:
        {"idChoice": int, "idUser": int, "idNPC": int, "idStorylet": int}
    """
    from flask import request, jsonify
    data = request.json
    if not data:
        return jsonify({"status": "error", "reason": "Missing request body"}), 400

    id_choice = data.get("idChoice")
    if id_choice is None:
        return jsonify({"status": "error", "reason": "Missing idChoice"}), 400

    # Delegate to phase_2 choice handlers based on idChoice
    if id_choice == 1:
        from phase_2_queries import idChoice_1_query
        return idChoice_1_query(
            idUser=data.get("idUser"),
            idNPC=data.get("idNPC"),
            idStorylet=data.get("idStorylet"),
        )
    elif id_choice == 3:
        from phase_2_queries import idChoice_3_query
        return idChoice_3_query(
            idUser=data.get("idUser"),
            idNPC=data.get("idNPC"),
            idStorylet=data.get("idStorylet"),
        )
    else:
        return jsonify({"status": "error", "reason": f"Unknown idChoice: {id_choice}"}), 400

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