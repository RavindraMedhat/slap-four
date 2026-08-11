class GameError(Exception):
    """Raised for any user-facing game-rule violation - the UI shows the
    message directly via st.error(), no error codes needed."""
