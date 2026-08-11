"""Room lifecycle: create_room, join_room."""

from firebase_admin import firestore
from firebase_functions import https_fn

from .common import db, generate_unique_room_code, get_room_or_raise, require_auth
from .deck import MAX_PLAYERS, MIN_PLAYERS

ERR = https_fn.FunctionsErrorCode


def create_room(req: https_fn.CallableRequest):
    uid = require_auth(req)
    display_name = (req.data or {}).get("display_name", "").strip()
    player_count = (req.data or {}).get("player_count")
    # Off by default - "just playing for points" (the penaltyCount tally).
    # When enabled, the round winner also gets to write a free-text penalty
    # for the loser(s) to actually go do.
    custom_penalties = bool((req.data or {}).get("custom_penalties", False))

    if not display_name:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "display_name is required.")
    if not isinstance(player_count, int) or not (MIN_PLAYERS <= player_count <= MAX_PLAYERS):
        raise https_fn.HttpsError(
            ERR.INVALID_ARGUMENT, f"player_count must be an integer {MIN_PLAYERS}..{MAX_PLAYERS}."
        )

    firestore_db = db()
    rooms = firestore_db.collection("rooms")
    code = generate_unique_room_code(rooms)
    room_ref = rooms.document(code)
    player_ref = room_ref.collection("players").document(uid)

    batch = firestore_db.batch()
    batch.set(room_ref, {
        "code": code,
        "hostUid": uid,
        "status": "lobby",
        "config": {"playerCount": player_count, "customPenalties": custom_penalties},
        "seatOrder": [],
        "createdAt": firestore.SERVER_TIMESTAMP,
        "currentRoundNumber": 0,
        "round": None,
    })
    batch.set(player_ref, {
        "uid": uid,
        "displayName": display_name,
        "seatIndex": 0,
        "isHost": True,
        "connected": True,
        "joinedAt": firestore.SERVER_TIMESTAMP,
        "penaltyCount": 0,
    })
    batch.commit()

    return {"roomCode": code}


def join_room(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    display_name = (req.data or {}).get("display_name", "").strip()

    if not room_code:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code is required.")
    if not display_name:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "display_name is required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    players_ref = room_ref.collection("players")

    transaction = firestore_db.transaction()
    return _join_room_txn(transaction, room_ref, players_ref, uid, display_name)


@firestore.transactional
def _join_room_txn(transaction, room_ref, players_ref, uid, display_name):
    room_snap = get_room_or_raise(room_ref.get(transaction=transaction))
    room = room_snap.to_dict()

    existing_players = list(players_ref.get(transaction=transaction))
    existing_by_uid = {p.id: p for p in existing_players}

    my_player_ref = players_ref.document(uid)
    if uid in existing_by_uid:
        # Idempotent reconnect: same player rejoining (e.g. after a refresh).
        transaction.update(my_player_ref, {
            "displayName": display_name,
            "connected": True,
        })
        return {"roomCode": room["code"], "seatIndex": existing_by_uid[uid].get("seatIndex")}

    if room["status"] != "lobby":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "This room's game has already started.")
    if len(existing_players) >= room["config"]["playerCount"]:
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "This room is full.")

    seat_index = len(existing_players)
    transaction.set(my_player_ref, {
        "uid": uid,
        "displayName": display_name,
        "seatIndex": seat_index,
        "isHost": False,
        "connected": True,
        "joinedAt": firestore.SERVER_TIMESTAMP,
        "penaltyCount": 0,
    })
    return {"roomCode": room["code"], "seatIndex": seat_index}


def leave_room(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    if not room_code:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code is required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    transaction = firestore_db.transaction()
    return _leave_room_txn(transaction, room_ref, uid)


@firestore.transactional
def _leave_room_txn(transaction, room_ref, uid):
    room_snap = get_room_or_raise(room_ref.get(transaction=transaction))
    room = room_snap.to_dict()

    if room["status"] != "lobby":
        raise https_fn.HttpsError(
            ERR.FAILED_PRECONDITION, "Can't leave once the game has started - you can only go offline."
        )

    players_ref = room_ref.collection("players")
    players = list(players_ref.get(transaction=transaction))
    if not any(p.id == uid for p in players):
        return {"roomDeleted": False}  # Already not in the room; idempotent no-op.

    remaining = sorted((p for p in players if p.id != uid), key=lambda p: p.get("seatIndex"))

    if not remaining:
        transaction.delete(players_ref.document(uid))
        transaction.delete(room_ref)
        return {"roomDeleted": True}

    # Re-number remaining seats to stay contiguous 0..k-1, since join_room
    # assigns new seats as len(existing_players) and would otherwise collide
    # with whatever seatIndex the leaving player leaves behind a gap at.
    for i, p in enumerate(remaining):
        if p.get("seatIndex") != i:
            transaction.update(p.reference, {"seatIndex": i})

    transaction.delete(players_ref.document(uid))

    if room["hostUid"] == uid:
        new_host_uid = remaining[0].id
        transaction.update(room_ref, {"hostUid": new_host_uid})
        transaction.update(players_ref.document(new_host_uid), {"isHost": True})

    return {"roomDeleted": False}
