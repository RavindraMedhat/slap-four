"""Shared helpers used across the callable Cloud Functions."""

import random

from firebase_admin import firestore
from firebase_functions import https_fn

ROOM_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I ambiguity
ROOM_CODE_LENGTH = 5
ROOM_CODE_GEN_ATTEMPTS = 5


def db():
    return firestore.client()


def require_auth(req: https_fn.CallableRequest) -> str:
    """Return the caller's uid, raising HttpsError if unauthenticated."""
    if req.auth is None:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.UNAUTHENTICATED, "Sign in required."
        )
    return req.auth.uid


def get_room_or_raise(room_snapshot):
    """Validate an already-fetched DocumentSnapshot for a room.

    Callers are responsible for fetching the snapshot themselves (plain
    `ref.get()` outside a transaction, or `ref.get(transaction=transaction)`
    inside one) so this helper works correctly in both contexts.
    """
    if not room_snapshot.exists:
        raise https_fn.HttpsError(
            https_fn.FunctionsErrorCode.NOT_FOUND, "Room not found."
        )
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
    raise https_fn.HttpsError(
        https_fn.FunctionsErrorCode.INTERNAL, "Could not generate a room code, try again."
    )
