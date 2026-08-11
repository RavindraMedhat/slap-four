"""Room lifecycle: create_room, join_room, leave_room."""

from google.cloud import firestore

from .common import generate_unique_room_code, get_room_or_raise
from .deck import MAX_PLAYERS, MIN_PLAYERS
from .errors import GameError


def create_room(db, uid, display_name, player_count, custom_penalties):
    display_name = (display_name or "").strip()
    if not display_name:
        raise GameError("Your name is required.")
    if not isinstance(player_count, int) or not (MIN_PLAYERS <= player_count <= MAX_PLAYERS):
        raise GameError(f"player_count must be an integer {MIN_PLAYERS}..{MAX_PLAYERS}.")

    rooms = db.collection("rooms")
    code = generate_unique_room_code(rooms)
    room_ref = rooms.document(code)
    player_ref = room_ref.collection("players").document(uid)

    batch = db.batch()
    batch.set(room_ref, {
        "code": code,
        "hostUid": uid,
        "status": "lobby",
        "config": {"playerCount": player_count, "customPenalties": bool(custom_penalties)},
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


def join_room(db, uid, room_code, display_name):
    room_code = (room_code or "").strip().upper()
    display_name = (display_name or "").strip()
    if not room_code:
        raise GameError("Room code is required.")
    if not display_name:
        raise GameError("Your name is required.")

    room_ref = db.collection("rooms").document(room_code)
    players_ref = room_ref.collection("players")

    transaction = db.transaction()
    return _join_room_txn(transaction, room_ref, players_ref, uid, display_name)


@firestore.transactional
def _join_room_txn(transaction, room_ref, players_ref, uid, display_name):
    room = get_room_or_raise(room_ref.get(transaction=transaction)).to_dict()

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
        raise GameError("This room's game has already started.")
    if len(existing_players) >= room["config"]["playerCount"]:
        raise GameError("This room is full.")

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


def leave_room(db, uid, room_code):
    room_code = (room_code or "").strip().upper()
    if not room_code:
        raise GameError("Room code is required.")

    room_ref = db.collection("rooms").document(room_code)
    transaction = db.transaction()
    return _leave_room_txn(transaction, room_ref, uid)


@firestore.transactional
def _leave_room_txn(transaction, room_ref, uid):
    room = get_room_or_raise(room_ref.get(transaction=transaction)).to_dict()

    if room["status"] != "lobby":
        raise GameError("Can't leave once the game has started - you can only go offline.")

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
