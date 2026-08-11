const SUIT_SYMBOLS = { S: "♠", H: "♥", D: "♦", C: "♣" };
const RED_SUITS = new Set(["H", "D"]);

const TIER_INFO = {
  single: { label: "Single Pressure", detail: "Only the last player to slap is penalized." },
  super: { label: "Super Pressure", detail: "The last TWO players to slap are penalized." },
  ultimate_super: { label: "Ultimate Super Pressure", detail: "The last THREE players to slap are penalized." },
};

// Guards against firing pass_card more than once for the same auto-claim
// while the call is in flight (render() can re-run from unrelated snapshot
// updates - e.g. presence - before the room doc flips out of "passing").
let autoResolving = false;

export function renderHand(panel, ctx) {
  const cards = ctx.hand || [];
  const canPass = ctx.room.status === "passing" && ctx.room.round.holderUid === ctx.uid;

  if (canPass && !autoResolving) {
    const ultimateCardId = findUltimateDiscard(cards);
    if (ultimateCardId) {
      // The hand has a complete natural four-of-a-kind AND the Joker -
      // Ultimate Super Pressure is achievable, and it's always the best
      // possible outcome for whoever claims it. Don't wait for a tap on any
      // particular card - claim it immediately, the moment the qualifying
      // card lands in hand.
      autoResolving = true;
      panel.innerHTML = `<p class="hand-title">Four of a kind plus the Joker - claiming Ultimate Super Pressure…</p>`;
      ctx.call("pass_card", { room_code: ctx.roomCode, card_id: ultimateCardId, decline_win: false })
        .catch(() => {})
        .finally(() => { autoResolving = false; });
      return;
    }
  }

  panel.innerHTML = `
    <p class="hand-title">Your hand (${cards.length} card${cards.length === 1 ? "" : "s"})${canPass ? " — tap one to pass" : ""}</p>
    <div class="hand-cards">
      ${cards.map((card) => cardButtonHtml(card, canPass)).join("")}
    </div>
  `;

  if (!canPass) return;

  panel.querySelectorAll("[data-card-id]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const cardId = btn.dataset.cardId;
      const discardedCard = cards.find((c) => c.id === cardId);
      const kept4 = cards.filter((c) => c.id !== cardId);
      const tier = classifyWin(discardedCard, kept4);
      let declineWin = false;

      // Only ask "slap now, or keep playing instead" when declining would be
      // a REAL choice - i.e. some other card in hand could be discarded
      // instead without winning at all. If every possible discard from this
      // hand wins something, there's nothing to "keep playing" toward, so
      // just take the win immediately with no prompt. (A hand that also
      // offers Ultimate Super Pressure never reaches this code at all - it
      // auto-resolves above before any cards are even rendered as clickable.)
      if (tier && hasEscapeCard(cards)) {
        const proceed = await confirmSlap(panel, kept4, tier);
        declineWin = !proceed;
      }

      panel.querySelectorAll("[data-card-id]").forEach((b) => (b.disabled = true));
      try {
        await ctx.call("pass_card", { room_code: ctx.roomCode, card_id: cardId, decline_win: declineWin });
      } catch (_) {
        renderHand(panel, ctx);
      }
    });
  });
}

// Mirrors functions/game/deck.py's classify_win - the server is the actual
// authority (it recomputes this itself from the real hand), this is only
// used to preview the outcome to the player before they commit.
function classifyWin(discardedCard, kept4) {
  if (kept4.length !== 4) return null;
  const keptRanks = kept4.map((c) => c.rank);
  const discardedIsJoker = discardedCard.rank === "JOKER";

  if (keptRanks.includes("JOKER")) {
    const nonJoker = keptRanks.filter((r) => r !== "JOKER");
    const allSame = nonJoker.length === 3 && new Set(nonJoker).size === 1;
    return allSame && !discardedIsJoker ? "super" : null;
  }

  if (new Set(keptRanks).size === 1) {
    return discardedIsJoker ? "ultimate_super" : "single";
  }
  return null;
}

// If `hand` contains the Joker and a complete natural four-of-a-kind among
// the other 4 cards, discarding the Joker wins Ultimate Super Pressure -
// return its card id. Otherwise null (Ultimate isn't reachable from this hand).
function findUltimateDiscard(hand) {
  const joker = hand.find((c) => c.rank === "JOKER");
  if (!joker) return null;
  const kept4 = hand.filter((c) => c.id !== joker.id);
  return classifyWin(joker, kept4) === "ultimate_super" ? joker.id : null;
}

// True if some card in `hand` could be discarded WITHOUT winning anything -
// i.e. declining the current winning discard would lead somewhere real.
function hasEscapeCard(hand) {
  return hand.some((c) => {
    const kept4 = hand.filter((x) => x.id !== c.id);
    return classifyWin(c, kept4) === null;
  });
}

function describeCombo(kept4, tier) {
  const rank = kept4.find((c) => c.rank !== "JOKER").rank;
  return tier === "super" ? `three ${rank}s plus the Joker` : `four ${rank}s`;
}

function confirmSlap(panel, kept4, tier) {
  const info = TIER_INFO[tier];
  return new Promise((resolve) => {
    panel.innerHTML = `
      <p class="hand-title">That discard completes ${describeCombo(kept4, tier)} - ${info.label}!</p>
      <div class="pressure-choices">
        <button class="pressure-choice" data-confirm>
          <strong>Slap now - ${info.label}</strong>
          <span>${info.detail}</span>
        </button>
        <button id="pressure-cancel" class="secondary">
          Keep playing instead - pass this card without slapping, and stay sitting on your set
        </button>
      </div>
    `;
    panel.querySelector("[data-confirm]").addEventListener("click", () => resolve(true));
    panel.querySelector("#pressure-cancel").addEventListener("click", () => resolve(false));
  });
}

function cardButtonHtml(card, interactive) {
  if (card.rank === "JOKER") {
    return `<button class="playing-card joker" data-card-id="${card.id}" ${interactive ? "" : "disabled"}>JOKER</button>`;
  }
  const isRed = RED_SUITS.has(card.suit);
  return `
    <button class="playing-card ${isRed ? "red" : ""}" data-card-id="${card.id}" ${interactive ? "" : "disabled"}>
      <span>${card.rank}</span>
      <span class="suit">${SUIT_SYMBOLS[card.suit] || ""}</span>
    </button>
  `;
}
