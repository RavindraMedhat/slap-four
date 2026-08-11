from datetime import datetime, timezone

import streamlit as st

from game import slap as slap_logic
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
    already_slapped = uid in (slap_state.get("slaps") or {})
    is_host = room["hostUid"] == uid

    st.subheader(f"{winner['displayName'] if winner else 'Someone'} got four {slap_state['winningRank']}s!")
    st.markdown(revealed_hand_html(slap_state.get("keptCards"), slap_state.get("discardedCard")), unsafe_allow_html=True)

    tier_label = PRESSURE_LABELS.get(slap_state["pressureMode"], slap_state["pressureMode"])
    if is_winner:
        st.success(f"{tier_label} called - you're safe this round.")
    else:
        st.error(f"{tier_label} called - SLAP THE TABLE NOW!")
        if st.button(
            "SLAPPED ✅" if already_slapped else "👋 SLAP!",
            type="primary",
            disabled=already_slapped,
            key="slap_btn",
            use_container_width=True,
        ):
            ctx["call"](slap_logic.slap, ctx["room_code"])

    slaps = slap_state.get("slaps") or {}
    if slaps:
        ordered = sorted(slaps.items(), key=lambda kv: kv[1])
        names = []
        for i, (slap_uid, _) in enumerate(ordered, start=1):
            p = next((pp for pp in players if pp["uid"] == slap_uid), None)
            names.append(f"{i}. {p['displayName'] if p else '?'}")
        st.caption(" · ".join(names))
    else:
        st.caption("Nobody has slapped yet.")

    if is_host:
        started_at = slap_state.get("startedAt")
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds() if started_at else 0
        ready = elapsed >= slap_logic.MIN_HOST_FORCE_RESOLVE_SECONDS
        label = (
            "Force resolve (someone's stalling)"
            if ready
            else f"Force resolve (available in {int(slap_logic.MIN_HOST_FORCE_RESOLVE_SECONDS - elapsed)}s)"
        )
        if st.button(label, disabled=not ready, key="force_resolve_btn"):
            ctx["call"](slap_logic.resolve_round, ctx["room_code"])
