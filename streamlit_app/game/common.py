"""Shared helpers used across game logic modules."""

import random

from .errors import GameError

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
ROOM_CODE_LENGTH = 5
ROOM_CODE_GEN_ATTEMPTS = 5


def get_room_or_raise(room_snapshot):
    """Validate an already-fetched DocumentSnapshot for a room.

    Callers are responsible for fetching the snapshot themselves (plain
    `ref.get()` outside a transaction, or `ref.get(transaction=transaction)`
    inside one) so this helper works correctly in both contexts.
    """
    if not room_snapshot.exists:
        raise GameError("Room not found.")
    return room_snapshot


def generate_unique_room_code(room_collection):
    """Generate a room code that doesn't currently exist. Not itself
    race-free against a simultaneous create - join_room/create_room
    collisions are astronomically unlikely at this alphabet/length and are
    not otherwise guarded against."""
    for _ in range(ROOM_CODE_GEN_ATTEMPTS):
        code = "".join(random.choices(ROOM_CODE_ALPHABET, k=ROOM_CODE_LENGTH))
        if not room_collection.document(code).get().exists:
            return code
    raise GameError("Could not generate a room code, try again.")
