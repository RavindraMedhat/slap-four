// Fewer penalties is better - rank with the lowest penalty count first, and
// mark whoever's currently tied for the lead. Shared by the header Scores
// panel (app.js) and the round-result screen so both agree on the same ranking.
export function renderRankedRoster(players, myUid) {
  const sorted = [...players].sort(
    (a, b) => a.penaltyCount - b.penaltyCount || a.seatIndex - b.seatIndex
  );
  const lead = sorted.length ? sorted[0].penaltyCount : 0;
  return sorted
    .map((p, i) => {
      const isLeading = p.penaltyCount === lead;
      return `
        <li>
          <span>${i + 1}. ${escapeHtml(p.displayName)}${p.uid === myUid ? " (you)" : ""}${isLeading ? " 🏆" : ""}</span>
          <span class="penalty-count ${isLeading ? "good" : ""}">${p.penaltyCount} penalt${p.penaltyCount === 1 ? "y" : "ies"}</span>
        </li>`;
    })
    .join("");
}

const SUIT_SYMBOLS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const RED_SUITS = new Set(["H", "D"]);

// A static (non-interactive) card visual, for revealing a winning hand to
// everyone - not just the winner's own private hand panel. `dimmed` marks
// the discarded card (out of play) distinctly from the 4 kept cards.
export function cardVisualHtml(card, { dimmed = false } = {}) {
  const isJoker = card.rank === "JOKER";
  const classes = ["playing-card", "static"];
  if (isJoker) classes.push("joker");
  else if (RED_SUITS.has(card.suit)) classes.push("red");
  if (dimmed) classes.push("dimmed");

  const inner = isJoker
    ? "JOKER"
    : `<span>${card.rank}</span><span class="suit">${SUIT_SYMBOLS[card.suit] || ""}</span>`;
  return `<div class="${classes.join(" ")}">${inner}</div>`;
}

// Renders the 4 kept cards plus the discarded card (dimmed, with a caption)
// as a labeled "revealed hand" strip - used on both the slap and result
// screens so every player can see the actual combo, not just trust the text.
export function revealedHandHtml(keptCards, discardedCard) {
  if (!keptCards || !keptCards.length) return "";
  const keptHtml = keptCards.map((c) => cardVisualHtml(c)).join("");
  const discardedHtml = discardedCard
    ? `<div class="discarded-card">${cardVisualHtml(discardedCard, { dimmed: true })}<span class="discarded-label">discarded</span></div>`
    : "";
  return `
    <div class="revealed-hand">
      <div class="hand-cards">${keptHtml}${discardedHtml}</div>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
