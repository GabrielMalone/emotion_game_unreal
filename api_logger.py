"""
Shared API-error logger — all TTS/LLM API failures go to the root
logger (server.log) via stderr, no separate file.
"""

import logging
import os

api_log = logging.getLogger("api_errors")
api_log.setLevel(logging.DEBUG)

# Prevent duplicate handlers if module is reloaded
if not any(isinstance(h, logging.StreamHandler) for h in api_log.handlers):
    sh = logging.StreamHandler()
    sh.setLevel(logging.WARNING)  # terminal only sees WARNING+
    sh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] api: %(message)s",
        datefmt="%H:%M:%S",
    ))
    api_log.addHandler(sh)
    # Do NOT set propagate=False — let messages reach root → server.log
