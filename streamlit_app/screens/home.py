import streamlit as st

from game import rooms


def render(ctx):
    st.write(
        "Collect four of a kind, then be the fastest to slap the table. "
        "The pressure level (how many of the slowest slappers get penalized) "
        "is decided automatically by which cards complete the win."
    )
    tab_create, tab_join = st.tabs(["Create Room", "Join Room"])

    with tab_create:
        name = st.text_input("Your name", value=st.session_state.display_name, key="create_name")
        count = st.selectbox("Number of players", [3, 4, 5, 6, 7, 8], key="create_count")
        custom = st.checkbox(
            "Let the winner write a custom penalty (otherwise just playing for points)",
            key="create_custom",
        )
        if st.button("Create Room", type="primary", key="create_submit"):
            if not name.strip():
                st.warning("Enter your name first.")
            else:
                st.session_state.display_name = name.strip()
                result = ctx["call"](rooms.create_room, name.strip(), int(count), custom)
                if result is not None:
                    ctx["set_room"](result["roomCode"])
                    st.rerun()

    with tab_join:
        prefill_code = st.query_params.get("room", "")
        name2 = st.text_input("Your name", value=st.session_state.display_name, key="join_name")
        code = st.text_input(
            "Room code", value=prefill_code, max_chars=5, key="join_code"
        ).strip().upper()
        if st.button("Join Room", type="primary", key="join_submit"):
            if not name2.strip() or not code:
                st.warning("Enter your name and a room code.")
            else:
                st.session_state.display_name = name2.strip()
                result = ctx["call"](rooms.join_room, code, name2.strip())
                if result is not None:
                    ctx["set_room"](result["roomCode"])
                    st.rerun()
