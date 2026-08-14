"""Slap-race resolution: slap, resolve_round, set_penalty.

Ranking is by each player's own client-measured reaction time (ms from the
slap prompt appearing on their screen to their tap), reported by the client
and trusted as-is - not by server arrival order. Server arrival order would
conflate real reaction time with each player's network latency, which isn't
what a reflex game is supposed to measure. The tradeoff is that this trusts
a client-reported number, so a modified client could in principle report a
fake low value - accepted here since this is a casual game among friends.
"""

import math
import random
from datetime import datetime, timezone

from firebase_admin import firestore
from firebase_functions import https_fn, scheduler_fn

from .common import db, get_room_or_raise, require_auth

ERR = https_fn.FunctionsErrorCode

PENALTY_LAST_N = {"single": 1, "super": 2, "ultimate_super": 3}
MIN_HOST_FORCE_RESOLVE_SECONDS = 20
HARD_TIMEOUT_SECONDS = 60

# Requested by the repo owner: any player whose display name contains
# "ravi" (case-insensitive) has a 50% chance, per qualifying round, of
# being secretly rescued from a penalty they'd otherwise genuinely have
# earned - by treating their reaction time as the fastest of the table.
# Never applies to Ultimate Super Pressure. Everyone else's real reaction
# time is untouched.
RAVI_NAME_NEEDLE = "ravi"
RAVI_RESCUE_CHANCE = 0.5


def _resolve_order_and_penalties(seat_order, winner_uid, slaps, penalty_mode, player_names):
    non_winners = [u for u in seat_order if u != winner_uid]
    seat_index_of = {u: i for i, u in enumerate(seat_order)}

    def ranked(effective_slaps):
        return sorted(non_winners, key=lambda u: (effective_slaps.get(u, math.inf), seat_index_of[u]))

    order = ranked(slaps)
    last_n = min(PENALTY_LAST_N[penalty_mode], len(order))
    penalized = order[-last_n:] if last_n > 0 else []

    if penalty_mode != "ultimate_super":
        rescue_uid = next(
            (u for u in penalized if RAVI_NAME_NEEDLE in (player_names.get(u) or "").lower()), None
        )
        if rescue_uid and random.random() < RAVI_RESCUE_CHANCE:
            rigged_slaps = dict(slaps)
            rigged_slaps[rescue_uid] = min(slaps.values(), default=0) - 1
            order = ranked(rigged_slaps)
            penalized = order[-last_n:] if last_n > 0 else []

    return order, penalized


def _apply_resolution(transaction, room_ref, room, slaps, player_names):
    order, penalized = _resolve_order_and_penalties(
        room["seatOrder"], room["round"]["slap"]["winnerUid"], slaps, room["round"]["slap"]["pressureMode"], player_names
    )
    transaction.update(room_ref, {
        "status": "round_end",
        "round.slap.slaps": slaps,
        "round.slap.order": order,
        "round.slap.penalizedUids": penalized,
        "round.slap.resolvedAt": firestore.SERVER_TIMESTAMP,
    })
    for penalized_uid in penalized:
        transaction.update(
            room_ref.collection("players").document(penalized_uid),
            {"penaltyCount": firestore.Increment(1)},
        )


def slap(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    if not room_code:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code is required.")
    try:
        reaction_ms = int((req.data or {}).get("reaction_ms"))
    except (TypeError, ValueError):
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "reaction_ms is required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    transaction = firestore_db.transaction()
    return _slap_txn(transaction, room_ref, uid, reaction_ms)


@firestore.transactional
def _slap_txn(transaction, room_ref, uid, reaction_ms):
    room_snap = get_room_or_raise(room_ref.get(transaction=transaction))
    room = room_snap.to_dict()

    if room["status"] != "slapping":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "Not currently in the slap phase.")

    slap_state = room["round"]["slap"]
    if uid == slap_state["winnerUid"]:
        # The round's winner is always exempt from the slap race.
        return {"reactionMs": 0, "resolved": False}

    slaps = dict(slap_state["slaps"] or {})
    if uid in slaps:
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "You already slapped.")

    slaps[uid] = reaction_ms

    non_winner_count = len(room["seatOrder"]) - 1
    resolved = len(slaps) >= non_winner_count

    if resolved:
        player_docs = room_ref.collection("players").get(transaction=transaction)
        player_names = {d.id: d.to_dict().get("displayName", "") for d in player_docs}
        _apply_resolution(transaction, room_ref, room, slaps, player_names)
    else:
        transaction.update(room_ref, {"round.slap.slaps": slaps})

    return {"reactionMs": reaction_ms, "resolved": resolved}


@firestore.transactional
def _resolve_round_txn(transaction, room_ref):
    room_snap = get_room_or_raise(room_ref.get(transaction=transaction))
    room = room_snap.to_dict()
    if room["status"] != "slapping":
        return  # Already resolved (e.g. the last slap beat us to it).

    slap_state = room["round"]["slap"]
    player_docs = room_ref.collection("players").get(transaction=transaction)
    player_names = {d.id: d.to_dict().get("displayName", "") for d in player_docs}
    _apply_resolution(transaction, room_ref, room, dict(slap_state["slaps"] or {}), player_names)


def resolve_round(req: https_fn.CallableRequest):
    """Host-forceable early resolution once MIN_HOST_FORCE_RESOLVE_SECONDS
    has elapsed, for when a straggler never slaps."""
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    if not room_code:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code is required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    room = get_room_or_raise(room_ref.get()).to_dict()

    if room["hostUid"] != uid:
        raise https_fn.HttpsError(ERR.PERMISSION_DENIED, "Only the host can force-resolve the round.")
    if room["status"] != "slapping":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "Not currently in the slap phase.")

    started_at = room["round"]["slap"]["startedAt"]
    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
    if elapsed < MIN_HOST_FORCE_RESOLVE_SECONDS:
        raise https_fn.HttpsError(
            ERR.FAILED_PRECONDITION,
            f"Wait at least {MIN_HOST_FORCE_RESOLVE_SECONDS}s before forcing resolution.",
        )

    _resolve_round_txn(firestore_db.transaction(), room_ref)
    return {}


@scheduler_fn.on_schedule(schedule="every 1 minutes")
def auto_resolve_stalled_rounds(event: scheduler_fn.ScheduledEvent) -> None:
    """Hard backstop: force-resolve any round stuck in 'slapping' for over
    HARD_TIMEOUT_SECONDS, so a disconnected player never permanently blocks
    the table."""
    firestore_db = db()
    now = datetime.now(timezone.utc)
    stalled = firestore_db.collection("rooms").where("status", "==", "slapping").stream()
    for room_snap in stalled:
        room = room_snap.to_dict()
        started_at = room["round"]["slap"]["startedAt"]
        if started_at is None:
            continue
        if (now - started_at).total_seconds() >= HARD_TIMEOUT_SECONDS:
            _resolve_round_txn(firestore_db.transaction(), room_snap.reference)


def set_penalty(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    penalty_text = (req.data or {}).get("penalty_text", "").strip()
    if not room_code or not penalty_text:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code and penalty_text are required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    transaction = firestore_db.transaction()
    return _set_penalty_txn(transaction, room_ref, uid, penalty_text)


@firestore.transactional
def _set_penalty_txn(transaction, room_ref, uid, penalty_text):
    room_snap = get_room_or_raise(room_ref.get(transaction=transaction))
    room = room_snap.to_dict()

    if not room["config"].get("customPenalties"):
        raise https_fn.HttpsError(
            ERR.FAILED_PRECONDITION, "This room is playing for points only - custom penalties are off."
        )
    if room["round"]["slap"]["winnerUid"] != uid:
        raise https_fn.HttpsError(ERR.PERMISSION_DENIED, "Only the round's winner can set the penalty.")
    if room["status"] != "round_end":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "The round hasn't been resolved yet.")
    if room["round"]["penalty"] is not None:
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "A penalty has already been set for this round.")

    transaction.update(room_ref, {
        "round.penalty": {"text": penalty_text, "setBy": uid, "setAt": firestore.SERVER_TIMESTAMP},
    })
    return {}
