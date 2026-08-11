"""Slap Four - Streamlit entrypoint.

Talks to Firestore directly via a service account (see game/firestore_client.py) -
no Cloud Functions, no Blaze billing plan required. Real-time-ish sync is via
periodic autorefresh (Streamlit has no push/websocket model to arbitrary
external services), faster during the slap race than during passing/lobby.
"""

import uuid

import streamlit as st
from streamlit_autorefresh import st_autorefresh

from game import slap as slap_logic
from game.errors import GameError
from game.firestore_client import get_db
from screens import home, lobby, passing, result, slap_screen

st.set_page_config(page_title="Slap Four", page_icon="🐯", layout="centered")

# --- Identity & active room persist via URL query params, so a page reload
# (or sharing the URL) doesn't lose who you are or which room you're in. ---
if "pid" not in st.query_params:
    st.query_params["pid"] = str(uuid.uuid4())
uid = st.query_params["pid"]

if "room_code" not in st.session_state:
    st.session_state.room_code = st.query_params.get("room")
if "display_name" not in st.session_state:
    st.session_state.display_name = ""

db = get_db()


def set_room(code):
    st.session_state.room_code = code
    if code:
        st.query_params["room"] = code
    elif "room" in st.query_params:
        del st.query_params["room"]


def call(fn, *args, **kwargs):
    """Run a game-logic function, surfacing a GameError as a toast instead
    of a traceback - mirrors the web app's ctx.call() error handling."""
    try:
        return fn(db, uid, *args, **kwargs)
    except GameError as e:
        st.toast(f"⚠️ {e}")
        return None


def fetch_hand(room_code):
    snap = db.collection("rooms").document(room_code).collection("hands").document(uid).get()
    return snap.to_dict()["cards"] if snap.exists else None


st.markdown("## 🐯 Slap Four")

room_code = st.session_state.room_code

if not room_code:
    ctx = {"call": call, "set_room": set_room}
    home.render(ctx)
else:
    room_ref = db.collection("rooms").document(room_code)
    room_snap = room_ref.get()
    if not room_snap.exists:
        st.warning("That room no longer exists.")
        set_room(None)
        st.rerun()

    room = room_snap.to_dict()
    players = [p.to_dict() for p in room_ref.collection("players").stream()]
    players.sort(key=lambda p: p.get("seatIndex", 0))
    status = room["status"]

    # Poll faster during the slap race (reaction-time critical) than during
    # passing/lobby, to balance responsiveness against Firestore read cost.
    st_autorefresh(interval=500 if status == "slapping" else 1500, key="autorefresh")

    if status == "slapping":
        slap_logic.maybe_auto_resolve_stalled(db, room_code)

    header_cols = st.columns([3, 1, 1])
    with header_cols[0]:
        st.caption(f"Room code: **{room_code}**")
    with header_cols[1]:
        with st.popover("🏆 Scores"):
            ranked = sorted(players, key=lambda p: (p.get("penaltyCount", 0), p.get("seatIndex", 0)))
            lead = ranked[0].get("penaltyCount", 0) if ranked else 0
            for i, p in enumerate(ranked, start=1):
                you = " (you)" if p["uid"] == uid else ""
                count = p.get("penaltyCount", 0)
                trophy = " 🏆" if count == lead else ""
                plural = "y" if count == 1 else "ies"
                st.write(f"{i}. {p['displayName']}{you}{trophy} — {count} penalt{plural}")
    with header_cols[2]:
        leave_label = "Leave" if status == "lobby" else "Exit"
        if st.button(leave_label, key="leave_btn"):
            if status == "lobby":
                from game import rooms
                call(rooms.leave_room, room_code)
            set_room(None)

    ctx = {
        "call": call,
        "set_room": set_room,
        "room": room,
        "players": players,
        "room_code": room_code,
        "uid": uid,
    }

    if status == "lobby":
        lobby.render(ctx)
    elif status == "passing":
        ctx["hand"] = fetch_hand(room_code)
        passing.render(ctx)
    elif status == "slapping":
        ctx["hand"] = fetch_hand(room_code)
        slap_screen.render(ctx)
    elif status == "round_end":
        ctx["hand"] = fetch_hand(room_code)
        result.render(ctx)
    else:
        st.error(f"Unknown room state: {status}")
