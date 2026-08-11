export function renderPassing(root, ctx) {
  const { room, players, uid } = ctx;
  const holderUid = room.round.holderUid;
  const holder = players.find((p) => p.uid === holderUid);
  const isMyTurn = holderUid === uid;

  root.innerHTML = `
    <div class="card-panel">
      <h2>Round ${room.currentRoundNumber}</h2>
      <div class="holder-banner">
        ${
          isMyTurn
            ? "Your turn! Tap a card below to pass it on."
            : `Waiting for ${escapeHtml(holder ? holder.displayName : "…")} to pass a card…`
        }
      </div>
      <p class="muted" style="margin-top:16px;">
        Passes so far this round: ${room.round.passSeq}. Keep four of a kind in hand to win!
      </p>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
