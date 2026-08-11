import streamlit as st

from game import round_flow, slap as slap_logic
from .ui_helpers import revealed_hand_html

PRESSURE_LABELS = {
    "single": "Single Pressure",
    "super": "Super Pressure",
    "ultimate_super": "Ultimate Super Pressure",
}


def render(ctx):
    room = ctx["room"]
    players = ctx["players"]
    uid = ctx["uid"]
    slap_state = room["round"]["slap"]
    winner_uid = slap_state["winnerUid"]
    winner = next((p for p in players if p["uid"] == winner_uid), None)
    is_winner = uid == winner_uid
    is_host = room["hostUid"] == uid
    penalized = set(slap_state.get("penalizedUids") or [])

    st.subheader(f"Round {room['currentRoundNumber']} Result")
    tier_label = PRESSURE_LABELS.get(slap_state["pressureMode"], slap_state["pressureMode"])
    st.write(
        f"**{winner['displayName'] if winner else '?'}** collected four "
        f"{slap_state['winningRank']}s, called **{tier_label}**, and won the slap race!"
    )
    st.markdown(revealed_hand_html(slap_state.get("keptCards"), slap_state.get("discardedCard")), unsafe_allow_html=True)

    order = slap_state.get("order") or []
    for i, slap_uid in enumerate(order, start=1):
        p = next((pp for pp in players if pp["uid"] == slap_uid), None)
        name = p["displayName"] if p else "?"
        if slap_uid in penalized:
            st.markdown(f":red[**{i}. {name} — penalized**]")
        else:
            st.write(f"{i}. {name}")

    if room["config"].get("customPenalties"):
        penalty = room["round"].get("penalty")
        if penalty:
            st.info(f'Penalty: "{penalty["text"]}"')
        elif is_winner:
            text = st.text_input("Choose a penalty for the loser(s)", max_chars=80, key="penalty_text")
            if st.button("Set Penalty", key="set_penalty_btn"):
                if not text.strip():
                    st.warning("Enter a penalty first.")
                else:
                    ctx["call"](slap_logic.set_penalty, ctx["room_code"], text.strip())
        else:
            st.caption(f"Waiting for {winner['displayName'] if winner else 'the winner'} to choose a penalty…")

    st.divider()
    st.write("**🏆 Scoreboard**")
    ranked = sorted(players, key=lambda p: (p.get("penaltyCount", 0), p.get("seatIndex", 0)))
    lead = ranked[0].get("penaltyCount", 0) if ranked else 0
    for i, p in enumerate(ranked, start=1):
        you = " (you)" if p["uid"] == uid else ""
        count = p.get("penaltyCount", 0)
        trophy = " 🏆" if count == lead else ""
        plural = "y" if count == 1 else "ies"
        st.write(f"{i}. {p['displayName']}{you}{trophy} — {count} penalt{plural}")

    if is_host:
        if st.button("Start Next Round", type="primary", key="next_round_btn"):
            ctx["call"](round_flow.start_next_round, ctx["room_code"])
