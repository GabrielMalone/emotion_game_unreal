import os
import re
from datetime import datetime

from turnContext import EmotionGameTurn
from db import get_cursor

# ------------------------------------------------------------------
#  Markdown game log (file-based, updated live as the game is played)
# ------------------------------------------------------------------

LOG_DIR: str = os.path.join(os.path.dirname(__file__), "logs")

# Regex that matches most emoji ranges (kept broad to catch new additions)
_STRIP_EMOJI = re.compile(
    "[\U0001F300-\U0001F9FF"      # Misc symbols, emoticons, supplemental
    "\U0001FA00-\U0001FA6F"       # Chess symbols, etc.
    "\U0001FA70-\U0001FAFF"       # More symbols
    "\u2600-\u27BF"               # Misc dingbats/arrows
    "\u2B50"                       # Star
    "\U0001F1E0-\U0001F1FF"       # Flags
    "\U0001F900-\U0001F9FF"       # Supplemental symbols
    "\U0001F600-\U0001F64F"       # Emoticons
    "\U0001F680-\U0001F6FF"       # Transport
    "\U0001F300-\U0001F5FF"       # Misc symbols
    "\U0001F910-\U0001F9FF"       # More symbols
    "]",
    re.UNICODE,
)


def _sanitize_log_text(s: str) -> str:
    """Strip emoji characters from log strings."""
    return _STRIP_EMOJI.sub("", s)


def _game_log_path(id_user: int, id_npc: int) -> str:
    """Return the path to the game markdown log for a player+NPC session."""
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.join(LOG_DIR, f"game_{id_user}_{id_npc}.md")


def append_game_md_log(
    turn: EmotionGameTurn,
    event_type: str,
    detail: str = "",
) -> None:
    """Append a timestamped entry to the game's markdown log file.

    event_type: one of 'start', 'intro', 'correct', 'incorrect',
                'statement', 'share', 'round_end'
    """
    path = _game_log_path(turn.idUser, turn.idNPC)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    detail = _sanitize_log_text(detail)

    # Write a header if the file is brand new
    if not os.path.exists(path):
        header = _sanitize_log_text(
            f"# Emotion Game Log\n\n"
            f"**Player:** {turn.player_name or 'Unknown'}\n"
            f"**NPC ID:** {turn.idNPC}\n"
            f"**User ID:** {turn.idUser}\n"
            f"**Started:** {timestamp}\n\n"
            f"---\n\n"
        )
    else:
        header = ""

    title = event_type.replace("_", " ").title()

    entry = f"### [{timestamp}] {title}\n{detail}\n\n"

    with open(path, "a") as f:
        if header:
            f.write(header)
        f.write(entry)


# ------------------------------------------------------------------
def log_guess_attempt(
    turn: EmotionGameTurn,
    player_guess: str,
    correct: bool,
    feedback_text: str = "",
) -> int | None:
    """Insert a guess attempt into emotion_guess_attempt and return its idAttempt.

    Called on every player guess (correct or incorrect).
    """
    id_emotion = None
    if correct and turn.emotion_guessed_id:
        id_emotion = turn.emotion_guessed_id
    else:
        # For incorrect guesses we still need idEmotion — pull from active row
        active = get_active_emotion(turn)
        if active:
            id_emotion = active["idEmotion"]

    if id_emotion is None:
        return None  # can't log without an emotion

    with get_cursor() as (db, cursor):
        cursor.execute(
            """
            INSERT INTO emotion_guess_attempt
                (idUser, idNPC, idEmotion, player_guess, correct,
                 player_name, feedback_text, attemptedAt)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                turn.idUser,
                turn.idNPC,
                id_emotion,
                player_guess,
                1 if correct else 0,
                turn.player_name or "",
                feedback_text or "",
            ),
        )
        db.commit()
        return cursor.lastrowid


def update_share_story(turn: EmotionGameTurn, share_story: str) -> bool:
    """Update the latest guess attempt for this user/NPC with their share story.

    Called when the player shares a time they felt the emotion
    after a correct guess.
    """
    if not share_story.strip():
        return False

    with get_cursor() as (db, cursor):
        cursor.execute(
            """
            UPDATE emotion_guess_attempt
            SET share_story = %s
            WHERE idAttempt = (
                SELECT latest.idAttempt FROM (
                    SELECT idAttempt
                    FROM emotion_guess_attempt
                    WHERE idUser = %s
                      AND idNPC = %s
                    ORDER BY attemptedAt DESC
                    LIMIT 1
                ) latest
            )
            """,
            (share_story.strip(), turn.idUser, turn.idNPC),
        )
        db.commit()
        return cursor.rowcount > 0


def get_player_game_log(id_user: int, id_npc: int) -> list[dict]:
    """Return a nicely formatted game-session log for a player.

    Each row includes the emotion, the player's guess, whether it was
    correct, the NPC's feedback, and their share story (if any).
    Ordered chronologically.
    """
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute(
            """
            SELECT
                a.idAttempt,
                a.player_name,
                e.emotion,
                a.player_guess,
                a.correct,
                a.feedback_text,
                a.share_story,
                a.attemptedAt
            FROM emotion_guess_attempt a
            JOIN emotion e ON e.idEmotion = a.idEmotion
            WHERE a.idUser = %s
              AND a.idNPC = %s
            ORDER BY a.attemptedAt ASC
            """,
            (id_user, id_npc),
        )
        return cursor.fetchall()


# ------------------------------------------------------------------
def mark_emotion_guessed_correct(t: EmotionGameTurn):
    with get_cursor() as (db, cursor):
        cursor.execute("""
            UPDATE emotion_guess_game
            SET guessed_correctly = 1,
                active = 0,
                completedAt = NOW()
            WHERE idUser = %s
            AND idNPC = %s
            AND active = 1;
        """, (t.idUser, t.idNPC))
        db.commit()

# ------------------------------------------------------------------
def get_remaining_emotions(t: EmotionGameTurn) -> list[str]:
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute("""
            SELECT e.emotion
            FROM emotion e
            WHERE e.idEmotion NOT IN (
                SELECT g.idEmotion
                FROM emotion_guess_game g
                WHERE g.idUser = %s
                  AND g.idNPC = %s
                  AND g.guessed_correctly = 1
            )
            ORDER BY e.idEmotion ASC;
        """, (t.idUser, t.idNPC))
        rows = cursor.fetchall()
        return [r["emotion"] for r in rows]

# ------------------------------------------------------------------
def get_active_emotion(t: EmotionGameTurn) -> dict | None:
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute("""
            SELECT e.idEmotion, e.emotion
            FROM emotion_guess_game g
            JOIN emotion e ON e.idEmotion = g.idEmotion
            WHERE g.idUser = %s
              AND g.idNPC = %s
              AND g.active = 1
            LIMIT 1;
        """, (t.idUser, t.idNPC))
        return cursor.fetchone()

# ------------------------------------------------------------------
def get_num_correct(t: EmotionGameTurn) -> dict | None:
    with get_cursor(dictionary=True) as (_db, cursor):
        cursor.execute("""
            SELECT COUNT(*) AS num_correct
            FROM emotion_guess_game
            WHERE idUser = %s
              AND idNPC = %s
              AND guessed_correctly = 1;
        """, (t.idUser, t.idNPC))
        return cursor.fetchone()

# ------------------------------------------------------------------
def assign_next_emotion(t: EmotionGameTurn):
    """Assign the next unused emotion atomically.

    The three statements (deactivate old, find next, insert new) must
    be transactional so a crash between steps doesn't leave the game
    with no active emotion.
    """
    from db import transactional
    with transactional(dictionary=True) as (db, cursor):

        # 1. Deactivate any currently active emotion (safety)
        cursor.execute("""
            UPDATE emotion_guess_game
            SET active = 0
            WHERE idUser = %s
              AND idNPC = %s
              AND active = 1;
        """, (t.idUser, t.idNPC))

        # 2. Find the next unused emotion (deterministic order!)
        cursor.execute("""
            SELECT e.idEmotion, e.emotion
            FROM emotion e
            LEFT JOIN emotion_guess_game g
              ON g.idEmotion = e.idEmotion
             AND g.idUser = %s
             AND g.idNPC = %s
            WHERE g.idEmotion IS NULL
            ORDER BY e.idEmotion ASC
            LIMIT 1;
        """, (t.idUser, t.idNPC))

        emotion = cursor.fetchone()
        if not emotion:
            db.commit()
            return None  # all emotions completed

        # 3. Insert as the new active emotion
        cursor.execute("""
            INSERT INTO emotion_guess_game (
                idUser,
                idNPC,
                idEmotion,
                active,
                described,
                guessed_correctly
            )
            VALUES (%s, %s, %s, 1, 1, 0);
        """, (t.idUser, t.idNPC, emotion["idEmotion"]))

        db.commit()
        return emotion
