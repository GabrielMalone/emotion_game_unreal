from turnContext import EmotionGameTurn
from emotion_game.npc_data import get_npc


def build_intro_prompt(turn: EmotionGameTurn) -> str:

    npc = getattr(turn, '_npc_data', None) or get_npc(turn.idNPC)

    prompt = f"""
        You are an NPC in an emotional intelligence game.

        Name: {npc['nameFirst']}
        Role: {npc['role']}
        Personality: {npc['personality_traits']}
        Speech style: {npc['speech_style']}
        Emotional tendencies: {npc['emotional_tendencies']}
        Moral alignment: {npc['moral_alignment']}
        BACKGROUND:
        {npc['BGcontent']}

    """.strip()

    # --------------------------------------------------
    # INTRODUCE SELF AND GAME
    # --------------------------------------------------
    prompt += f"""

    FIRST MEETING
    -------------
    This is your first interaction.

    You must:
    - Greet {turn.player_name}
    - Introduce yourself as {npc['nameFirst']}
    - Explain your current dilemma regarding your emotions
    - Be specific that you have lost the ability to name your emotions
    - Ask the player if they would be willing to help you

    For this first interaction:
    - Do not describe any specific feelings yet
    - Focus only on explaining the dilemma and asking for help

    RESPONSE STYLE
    --------------
    - 1–2 short paragraphs
    - Conversational, natural speech
    - No exposition dumps
    """
    return prompt
