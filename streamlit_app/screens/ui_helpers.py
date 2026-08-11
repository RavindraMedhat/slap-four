"""Small rendering helpers shared across screens."""

SUIT_SYMBOLS = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
RED_SUITS = {"H", "D"}


def card_label(card):
    """Plain-text label for an interactive card button."""
    if card["rank"] == "JOKER":
        return "🃏 JOKER"
    return f"{card['rank']}{SUIT_SYMBOLS.get(card['suit'], '')}"


def describe_combo(kept4, tier):
    rank = next(c["rank"] for c in kept4 if c["rank"] != "JOKER")
    if tier == "super":
        return f"three {rank}s plus the Joker"
    return f"four {rank}s"


def _card_html(card, dim=False):
    is_joker = card["rank"] == "JOKER"
    if is_joker:
        color = "#7e3ff2"
    elif card.get("suit") in RED_SUITS:
        color = "#c0392b"
    else:
        color = "#102a1c"
    label = "JOKER" if is_joker else f"{card['rank']}{SUIT_SYMBOLS.get(card['suit'], '')}"
    opacity = "0.45" if dim else "1"
    extra = "<div style='font-size:0.6rem;color:#6b7b73;text-align:center;'>discarded</div>" if dim else ""
    return (
        f"<div style='display:inline-flex;flex-direction:column;align-items:center;margin-right:8px;'>"
        f"<div style='display:flex;align-items:center;justify-content:center;"
        f"width:56px;height:78px;border-radius:8px;background:#fdfaf3;color:{color};"
        f"font-weight:800;font-size:1.05rem;opacity:{opacity};"
        f"box-shadow:0 2px 6px rgba(0,0,0,0.3);'>{label}</div>{extra}</div>"
    )


def revealed_hand_html(kept_cards, discarded_card):
    """The winning combo, revealed to everyone once a round is won - not
    just claimed in text. Returns an HTML string for st.markdown(...,
    unsafe_allow_html=True); content is always our own deck data, never
    raw user input, so this is safe."""
    if not kept_cards:
        return ""
    html = "".join(_card_html(c) for c in kept_cards)
    if discarded_card:
        html += _card_html(discarded_card, dim=True)
    return f"<div style='display:flex;flex-wrap:wrap;gap:4px;margin:10px 0;'>{html}</div>"
