import streamlit as st

from game import round_flow
from game.deck import classify_win
from .ui_helpers import card_label, describe_combo

TIER_INFO = {
    "single": ("Single Pressure", "Only the last player to slap is penalized."),
    "super": ("Super Pressure", "The last TWO players to slap are penalized."),
    "ultimate_super": ("Ultimate Super Pressure", "The last THREE players to slap are penalized."),
}


def _has_escape_card(hand):
    """True if some card in `hand` could be discarded WITHOUT winning
    anything - i.e. declining the current winning discard leads somewhere
    real, so the confirm/decline prompt is worth showing."""
    return any(classify_win(c, [x for x in hand if x["id"] != c["id"]]) is None for c in hand)


def _find_ultimate_discard(hand):
    """If discarding the Joker would win Ultimate Super Pressure, return its
    id - Ultimate never waits for a specific click, it auto-resolves."""
    joker = next((c for c in hand if c["rank"] == "JOKER"), None)
    if not joker:
        return None
    kept4 = [c for c in hand if c["id"] != joker["id"]]
    return joker["id"] if classify_win(joker, kept4) == "ultimate_super" else None


def render(ctx):
    room = ctx["room"]
    players = ctx["players"]
    uid = ctx["uid"]
    hand = ctx["hand"] or []
    holder_uid = room["round"]["holderUid"]
    is_holder = holder_uid == uid

    st.subheader(f"Round {room['currentRoundNumber']}")
    if is_holder:
        st.info("Your turn! Pick a card below to pass it on.")
    else:
        holder = next((p for p in players if p["uid"] == holder_uid), None)
        st.info(f"Waiting for {holder['displayName'] if holder else '…'} to pass a card…")
    st.caption(
        f"Passes so far this round: {room['round']['passSeq']}. Keep four of a kind in hand to win!"
    )

    st.write("Your hand:")
    if not is_holder:
        st.write(" ".join(card_label(c) for c in hand) if hand else "—")
        return

    # Ultimate Super Pressure never waits for a specific click - the instant
    # the qualifying card is in hand, claim it immediately.
    ultimate_id = _find_ultimate_discard(hand)
    if ultimate_id:
        st.success("Four of a kind plus the Joker - claiming Ultimate Super Pressure…")
        ctx["call"](round_flow.pass_card, ctx["room_code"], ultimate_id, False)
        return

    pending_id = st.session_state.get("pending_discard")
    if pending_id and pending_id in [c["id"] for c in hand]:
        card = next(c for c in hand if c["id"] == pending_id)
        kept4 = [c for c in hand if c["id"] != pending_id]
        tier = st.session_state["pending_tier"]
        label, detail = TIER_INFO[tier]
        st.warning(f"That discard completes {describe_combo(kept4, tier)} - {label}!")
        st.caption(detail)
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"Slap now - {label}", type="primary", key="confirm_slap"):
                st.session_state.pop("pending_discard", None)
                st.session_state.pop("pending_tier", None)
                ctx["call"](round_flow.pass_card, ctx["room_code"], pending_id, False)
        with col2:
            if st.button("Keep playing instead", key="decline_slap"):
                st.session_state.pop("pending_discard", None)
                st.session_state.pop("pending_tier", None)
                ctx["call"](round_flow.pass_card, ctx["room_code"], pending_id, True)
        return

    st.caption("Tap a card to pass it:")
    cols = st.columns(len(hand))
    for col, card in zip(cols, hand):
        with col:
            if st.button(card_label(card), key=f"card_{card['id']}"):
                kept4 = [c for c in hand if c["id"] != card["id"]]
                tier = classify_win(card, kept4)
                if tier and _has_escape_card(hand):
                    st.session_state["pending_discard"] = card["id"]
                    st.session_state["pending_tier"] = tier
                    st.rerun()
                else:
                    ctx["call"](round_flow.pass_card, ctx["room_code"], card["id"], False)
