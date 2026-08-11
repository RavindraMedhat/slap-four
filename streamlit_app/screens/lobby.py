import streamlit as st

from game import round_flow


def render(ctx):
    room = ctx["room"]
    players = ctx["players"]
    uid = ctx["uid"]
    needed = room["config"]["playerCount"]
    is_host = room["hostUid"] == uid

    st.subheader("Waiting Room")

    base_url = st.secrets.get("app_base_url", "")
    if base_url:
        invite_link = f"{base_url.rstrip('/')}/?room={ctx['room_code']}"
        st.text_input("Invite link", value=invite_link, disabled=True, key="invite_link_display")
    else:
        st.caption("Share the room code above with the other players.")

    penalty_note = (
        "The winner can write a custom penalty."
        if room["config"].get("customPenalties")
        else "Playing for points only."
    )
    st.write(f"Needs exactly **{needed}** players. {penalty_note}")

    for p in players:
        dot = "🟢" if p.get("connected") else "⚪"
        host_tag = " :blue[host]" if p.get("isHost") else ""
        you_tag = " :orange[(you)]" if p["uid"] == uid else ""
        st.write(f"{dot} {p['displayName']}{you_tag}{host_tag}")

    if is_host:
        can_start = len(players) == needed
        label = "Start Game" if can_start else f"Waiting for {needed - len(players)} more player(s)…"
        if st.button(label, type="primary", disabled=not can_start, key="start_round_btn"):
            ctx["call"](round_flow.start_round, ctx["room_code"])
    else:
        st.caption("Waiting for the host to start the game…")
