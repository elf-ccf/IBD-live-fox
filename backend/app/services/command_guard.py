"""
In-memory concurrent command guard for the IBD Live assistant.

IMPORTANT LIMITATION:
    This guard uses a module-level threading.Lock and a set of
    active session UUIDs. It is suitable for the single-process
    Codespaces prototype only.

    Before running multiple Uvicorn workers or multiple backend
    instances this guard MUST be replaced with a PostgreSQL
    advisory lock, a unique command-job constraint in the
    database, or a distributed lock (such as Redis SETNX).
"""

import threading
import uuid

_lock = threading.Lock()
_active_sessions: set[uuid.UUID] = set()


def try_start_command(
    session_id: uuid.UUID,
) -> bool:
    """
    Attempt to claim the command slot for a session.

    Returns True if the slot was free and is now claimed.
    Returns False if another command is already running for
    this session.
    """
    with _lock:
        if session_id in _active_sessions:
            return False
        _active_sessions.add(session_id)
        return True


def finish_command(
    session_id: uuid.UUID,
) -> None:
    """
    Release the command slot for a session.

    Safe to call even if the session is not currently active.
    """
    with _lock:
        _active_sessions.discard(session_id)


def command_is_active(
    session_id: uuid.UUID,
) -> bool:
    """Return whether the session currently has an active command."""
    with _lock:
        return session_id in _active_sessions
