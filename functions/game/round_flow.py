"""Round lifecycle: start_round, pass_card, start_next_round."""

from firebase_admin import firestore
from firebase_functions import https_fn

from .common import db, get_room_or_raise, require_auth
from .deck import build_deck, classify_win, deal, next_seat, winning_rank

ERR = https_fn.FunctionsErrorCode


def _fresh_round_state(round_number, holder_uid):
    return {
        "number": round_number,
        "holderUid": holder_uid,
        "passSeq": 0,
        "slap": None,
        "penalty": None,
    }


def _deal_and_write(firestore_db, room_ref, seat_order, round_number, holder_uid):
    deck = build_deck(len(seat_order))
    hands = deal(deck, seat_order, holder_uid)

    batch = firestore_db.batch()
    for uid, cards in hands.items():
        batch.set(room_ref.collection("hands").document(uid), {"cards": cards})
    batch.update(room_ref, {
        "status": "passing",
        "seatOrder": seat_order,
        "round": _fresh_round_state(round_number, holder_uid),
    })
    batch.commit()


def start_round(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    if not room_code:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code is required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    room_snap = get_room_or_raise(room_ref.get())
    room = room_snap.to_dict()

    if room["hostUid"] != uid:
        raise https_fn.HttpsError(ERR.PERMISSION_DENIED, "Only the host can start the round.")
    if room["status"] != "lobby":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "Round already started.")

    players = list(room_ref.collection("players").stream())
    needed = room["config"]["playerCount"]
    if len(players) != needed:
        raise https_fn.HttpsError(
            ERR.FAILED_PRECONDITION,
            f"Need exactly {needed} players to start, have {len(players)}.",
        )

    seat_order = [p.id for p in sorted(players, key=lambda p: p.get("seatIndex"))]
    _deal_and_write(firestore_db, room_ref, seat_order, round_number=1, holder_uid=seat_order[0])

    room_ref.update({"currentRoundNumber": 1})
    return {}


def pass_card(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    card_id = (req.data or {}).get("card_id")
    # If this discard would complete a four-of-a-kind, the player can still
    # choose to decline claiming the win ("keep playing instead") - the card
    # is passed on exactly as normal, the relay just continues rather than
    # entering the slap phase. Irrelevant (ignored) for a non-winning discard.
    decline_win = bool((req.data or {}).get("decline_win", False))
    if not room_code or not card_id:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code and card_id are required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    transaction = firestore_db.transaction()
    return _pass_card_txn(transaction, room_ref, uid, card_id, decline_win)


@firestore.transactional
def _pass_card_txn(transaction, room_ref, uid, card_id, decline_win):
    room_snap = get_room_or_raise(room_ref.get(transaction=transaction))
    room = room_snap.to_dict()

    if room["status"] != "passing":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "Not currently in the passing phase.")
    if room["round"]["holderUid"] != uid:
        raise https_fn.HttpsError(ERR.PERMISSION_DENIED, "It is not your turn to pass.")

    seat_order = room["seatOrder"]
    next_uid = next_seat(seat_order, uid)

    hands_ref = room_ref.collection("hands")
    holder_hand_ref = hands_ref.document(uid)
    next_hand_ref = hands_ref.document(next_uid)

    holder_hand = holder_hand_ref.get(transaction=transaction).to_dict()
    next_hand = next_hand_ref.get(transaction=transaction).to_dict()

    holder_cards = holder_hand["cards"]
    if len(holder_cards) != 5:
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "You don't currently hold 5 cards.")

    matches = [c for c in holder_cards if c["id"] == card_id]
    if not matches:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "That card is not in your hand.")

    passed_card = matches[0]
    kept4 = [c for c in holder_cards if c["id"] != card_id]

    transaction.update(holder_hand_ref, {"cards": kept4})

    tier = None if decline_win else classify_win(passed_card, kept4)
    if tier:
        # The round ends right here - every hand gets completely overwritten
        # on the next deal anyway, so there's no point handing the discarded
        # card to the next player at all; it just disappears from play.
        rank_won = winning_rank(kept4)
        transaction.update(room_ref, {
            "status": "slapping",
            "round.slap": {
                "winnerUid": uid,
                "winningRank": rank_won,
                "pressureMode": tier,
                "discardedCard": passed_card,
                # Hands are private during play, but once a round is won the
                # winning combo is revealed to everyone as proof - same as a
                # real player showing their hand when they win.
                "keptCards": kept4,
                "slaps": {},
                "startedAt": firestore.SERVER_TIMESTAMP,
                "order": None,
                "penalizedUids": None,
                "resolvedAt": None,
            },
        })
        return {"win": True, "winningRank": rank_won, "pressureMode": tier}

    transaction.update(next_hand_ref, {"cards": next_hand["cards"] + [passed_card]})
    transaction.update(room_ref, {
        "round.holderUid": next_uid,
        "round.passSeq": room["round"]["passSeq"] + 1,
    })
    return {"win": False}


def start_next_round(req: https_fn.CallableRequest):
    uid = require_auth(req)
    room_code = (req.data or {}).get("room_code", "").strip().upper()
    if not room_code:
        raise https_fn.HttpsError(ERR.INVALID_ARGUMENT, "room_code is required.")

    firestore_db = db()
    room_ref = firestore_db.collection("rooms").document(room_code)
    room_snap = get_room_or_raise(room_ref.get())
    room = room_snap.to_dict()

    if room["hostUid"] != uid:
        raise https_fn.HttpsError(ERR.PERMISSION_DENIED, "Only the host can start the next round.")
    if room["status"] != "round_end":
        raise https_fn.HttpsError(ERR.FAILED_PRECONDITION, "The current round hasn't ended yet.")

    seat_order = room["seatOrder"]
    new_round_number = room["currentRoundNumber"] + 1
    start_index = (new_round_number - 1) % len(seat_order)
    holder_uid = seat_order[start_index]

    _deal_and_write(firestore_db, room_ref, seat_order, new_round_number, holder_uid)
    room_ref.update({"currentRoundNumber": new_round_number})
    return {}
