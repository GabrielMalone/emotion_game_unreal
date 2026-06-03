"""
One-shot script: design a custom ElevenLabs voice via Voice Design v3.

Generates 3 previews from a text description, saves each as an mp3 so you
can listen and pick.  Then saves the chosen one permanently and prints
the voice_id to plug into elevenlabsQueries.py DEFAULT_VOICE_ID.

Usage:
  python design_voice.py          # generate previews, save mp3s, ask which to keep
  python design_voice.py --id 7   # skip generation, save preview #7 permanently
"""

import os, sys, base64, argparse
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

load_dotenv(".env")

client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# ── Voice prompt ──────────────────────────────────────────────────────
# The more detail the better: age, gender, tone, accent, pacing, emotion.
VOICE_DESCRIPTION = (
    "A young female voice actress in her late 20s with an incredibly wide "
    "emotional range and theatrical, over-the-top delivery. Her voice can "
    "shift instantly from explosive joy to gut-wrenching sorrow, from "
    "simmering rage to trembling fear, from bright-eyed wonder to cold "
    "disgust — every emotion is dialed to eleven. Exaggerated pitch "
    "variation, dramatic pauses, breathless gasps, and sudden volume "
    "swings. Slight mid-Atlantic accent, crystal-clear studio quality. "
    "Think: a Broadway actress giving the performance of her life in a "
    "one-woman show, with every line dripping with intense, visceral emotion."
)

# Preview text — a mini script showcasing the full emotional range.
# Must be 100-1000 characters.  Each sentence hits a different emotion.
PREVIEW_TEXT = (
    "[happily] Oh my goodness, I can't believe it! This is the most wonderful "
    "day of my entire life! [laughs] I could just dance around this room forever!\n\n"
    "[sadly] But then... everything fell apart. [sighs] I was left all alone in "
    "the darkness, wondering if anyone would ever hold me again. [voice catches] "
    "The silence was unbearable.\n\n"
    "[angrily] How DARE you say that to me! After everything I've done for you! "
    "Get out! GET OUT right now before I lose my mind!\n\n"
    "[whispering] Please... please don't leave me here. [trembling] I can feel "
    "something watching us from the shadows. I'm so scared...\n\n"
    "[disgusted] Ugh, that is absolutely revolting! I have never seen anything "
    "so horrible in all my years. How can anyone live like this?\n\n"
    "[excited] Wait — is that what I think it is?! OH MY GOD, IT IS! "
    "[gasps] This changes everything! We have to tell everyone right now!"
)

PREVIEW_DIR = "./voice_previews"
os.makedirs(PREVIEW_DIR, exist_ok=True)


def generate_previews():
    """Call Voice Design API, save mp3s, return list of generated_voice_ids."""
    print("🎭  Designing voice...\n")
    print(f"Prompt: {VOICE_DESCRIPTION[:120]}...\n")

    result = client.text_to_voice.design(
        voice_description=VOICE_DESCRIPTION,
        text=PREVIEW_TEXT,
        model_id="eleven_ttv_v3",      # v3 voice design model
        guidance_scale=4.0,             # slightly lower = more creative range
        loudness=0.5,
        should_enhance=True,            # let AI expand the prompt
    )

    voice_ids = []
    for i, preview in enumerate(result.previews, 1):
        vid = preview.generated_voice_id
        voice_ids.append(vid)
        audio_bytes = base64.b64decode(preview.audio_base_64)
        path = f"{PREVIEW_DIR}/preview_{i}_{vid[:8]}.mp3"
        with open(path, "wb") as f:
            f.write(audio_bytes)
        print(f"  Preview #{i}  →  {path}  (voice_id: {vid})")

    print(f"\n✅  {len(voice_ids)} previews saved to {PREVIEW_DIR}/")
    print("\nListen to them, then run:")
    print(f"  python design_voice.py --id <1-{len(voice_ids)}>")
    return voice_ids


def save_voice(preview_index: int):
    """Re-generate (or load cached) previews and save the chosen one."""
    # We need to regenerate to get the same previews.
    # ElevenLabs may return different results each call, so we
    # re-generate and hope the user picks from the same batch.
    # Better approach: save generated_voice_ids to a file.
    import json
    ids_path = f"{PREVIEW_DIR}/_last_ids.json"

    if not os.path.exists(ids_path):
        print("❌  No saved preview IDs found. Run without --id first.")
        sys.exit(1)

    with open(ids_path) as f:
        data = json.load(f)

    if preview_index < 1 or preview_index > len(data["ids"]):
        print(f"❌  Invalid preview #. Choose 1-{len(data['ids'])}.")
        sys.exit(1)

    generated_voice_id = data["ids"][preview_index - 1]
    print(f"Saving preview #{preview_index} → permanent voice...")

    voice = client.text_to_voice.create(
        voice_name="Emotion Theatrical",
        voice_description=VOICE_DESCRIPTION,
        generated_voice_id=generated_voice_id,
    )

    voice_id = voice.voice_id
    print(f"\n✅  Voice saved!")
    print(f"    Voice ID:  {voice_id}")
    print(f"    Name:      {voice.voice_name}")
    print(f"\nAdd this to elevenlabsQueries.py:")
    print(f'    DEFAULT_VOICE_ID = "{voice_id}"  # custom Emotion Theatrical')
    print(f"\nAnd add to VOICE_REGISTRY:")
    print(f'    "{voice_id}": "Emotion Theatrical — custom, over-the-top emotional female",')
    return voice_id


def generate_and_save_ids():
    """Generate previews and save the IDs so --id can find them later."""
    import json
    result = client.text_to_voice.design(
        voice_description=VOICE_DESCRIPTION,
        text=PREVIEW_TEXT,
        model_id="eleven_ttv_v3",
        guidance_scale=4.0,
        loudness=0.5,
        should_enhance=True,
    )

    voice_ids = []
    for i, preview in enumerate(result.previews, 1):
        vid = preview.generated_voice_id
        voice_ids.append(vid)
        audio_bytes = base64.b64decode(preview.audio_base_64)
        path = f"{PREVIEW_DIR}/preview_{i}_{vid[:8]}.mp3"
        with open(path, "wb") as f:
            f.write(audio_bytes)
        print(f"  Preview #{i}  →  {path}")

    ids_path = f"{PREVIEW_DIR}/_last_ids.json"
    with open(ids_path, "w") as f:
        json.dump({"ids": voice_ids, "prompt": VOICE_DESCRIPTION}, f, indent=2)

    print(f"\n✅  {len(voice_ids)} previews saved. Listen and run:")
    print(f"    python design_voice.py --id <1-{len(voice_ids)}>")
    return voice_ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", type=int, help="Preview number to save permanently (1-3)")
    args = parser.parse_args()

    if args.id:
        save_voice(args.id)
    else:
        generate_and_save_ids()
