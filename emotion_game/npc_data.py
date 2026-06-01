"""
Shared NPC data access — single source of truth for NPC persona queries.

All prompt builders and game logic should use get_npc() instead of
duplicating the JOIN query across 6+ files.
"""

from typing import Optional
from db import get_cursor


def get_npc(idNPC: int) -> Optional[dict]:
    """Return NPC persona + background for a given idNPC, or None."""
    with get_cursor(dictionary=True) as (_conn, cursor):
        cursor.execute("""
            SELECT n.nameFirst, n.age, n.gender,
                   p.role, p.personality_traits,
                   p.emotional_tendencies, p.speech_style,
                   p.moral_alignment,
                   b.BGcontent
            FROM NPC n
            LEFT JOIN npc_persona p ON p.idNPC = n.idNPC
            LEFT JOIN background b ON b.idNPC = n.idNPC
            WHERE n.idNPC = %s
        """, (idNPC,))
        return cursor.fetchone()
