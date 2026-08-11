"""Deck construction, dealing, and seat-order helpers.

For N players the deck is four cards of each of N ranks plus one Joker
(4*N + 1 cards). One player is dealt 5 cards, everyone else 4, so the deal
always divides the deck exactly: 5 + 4*(N-1) == 4*N + 1.
"""

import random

RANK_SEQUENCE = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
SUITS = ["S", "H", "D", "C"]
JOKER_RANK = "JOKER"

MIN_PLAYERS = 3
MAX_PLAYERS = 8


def build_deck(n_players):
    """Return a shuffled deck of 4*n_players + 1 cards for n_players."""
    if not (MIN_PLAYERS <= n_players <= MAX_PLAYERS):
        raise ValueError(f"player_count must be between {MIN_PLAYERS} and {MAX_PLAYERS}")

    ranks = RANK_SEQUENCE[:n_players]
    deck = [
        {"id": f"{rank}-{suit}", "rank": rank, "suit": suit}
        for rank in ranks
        for suit in SUITS
    ]
    deck.append({"id": JOKER_RANK, "rank": JOKER_RANK, "suit": None})

    random.SystemRandom().shuffle(deck)
    return deck


def deal(deck, seat_order, holder_uid):
    """Deal `deck`: `holder_uid` gets 5 cards, everyone else in `seat_order`
    gets 4. `holder_uid` need not be `seat_order[0]` - the starting holder
    rotates seat by seat each round (see round_flow.py:start_next_round)."""
    hands = {holder_uid: deck[0:5]}
    idx = 5
    for uid in seat_order:
        if uid == holder_uid:
            continue
        hands[uid] = deck[idx: idx + 4]
        idx += 4
    return hands


def next_seat(seat_order, current_uid):
    """Return the uid of the seat after `current_uid` in `seat_order`."""
    i = seat_order.index(current_uid)
    return seat_order[(i + 1) % len(seat_order)]


def classify_win(discarded_card, kept_cards):
    """Return the pressure tier this exact discard achieves, or None if it
    isn't a winning discard at all. The tier is fully determined by the
    cards involved - it is never a free choice:

    - "single": kept 4 are all the same real rank, no Joker involved at all.
    - "super": kept 4 are 3 of the same real rank plus the Joker standing in
      as the 4th, and the discarded card is a genuine off-rank card (not
      the Joker).
    - "ultimate_super": kept 4 are a clean four-of-a-kind (no Joker among
      them) achieved specifically by discarding the Joker itself - i.e. the
      player was already sitting on a complete natural set *and* the Joker,
      and chose to shed the Joker rather than anything else.
    """
    if len(kept_cards) != 4:
        return None

    kept_ranks = [c["rank"] for c in kept_cards]
    discarded_is_joker = discarded_card["rank"] == JOKER_RANK

    if JOKER_RANK in kept_ranks:
        non_joker = [r for r in kept_ranks if r != JOKER_RANK]
        if len(non_joker) == 3 and len(set(non_joker)) == 1 and not discarded_is_joker:
            return "super"
        return None

    if len(set(kept_ranks)) == 1:
        return "ultimate_super" if discarded_is_joker else "single"

    return None


def winning_rank(kept_cards):
    """The real rank a winning kept-4 represents (ignores the Joker, if any)."""
    return next(c["rank"] for c in kept_cards if c["rank"] != JOKER_RANK)
