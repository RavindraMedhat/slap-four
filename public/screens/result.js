import { renderRankedRoster, revealedHandHtml } from "./shared.js";

const PRESSURE_LABELS = {
  single: "Single Pressure",
  super: "Super Pressure",
  ultimate_super: "Ultimate Super Pressure",
};

export function renderResult(root, ctx) {
  const { room, players, uid } = ctx;
  const slapState = room.round.slap;
  const winner = players.find((p) => p.uid === slapState.winnerUid);
  const isWinner = uid === slapState.winnerUid;
  const isHost = room.hostUid === uid;
  const penalizedSet = new Set(slapState.penalizedUids || []);

  const orderItems = (slapState.order || [])
    .map((slapUid) => {
      const p = players.find((pp) => pp.uid === slapUid);
      const cls = penalizedSet.has(slapUid) ? "penalized" : "";
      return `<li class="${cls}">${escapeHtml(p ? p.displayName : "?")}${penalizedSet.has(slapUid) ? " — penalized" : ""}</li>`;
    })
    .join("");

  root.innerHTML = `
    <div class="card-panel">
      <h2>Round ${room.currentRoundNumber} Result</h2>
      <p><span style="color:var(--accent); font-weight:700;">${escapeHtml(winner ? winner.displayName : "?")}</span> collected four ${escapeHtml(String(slapState.winningRank))}s, called <strong>${PRESSURE_LABELS[slapState.pressureMode] || slapState.pressureMode}</strong>, and won the slap race!</p>
      ${revealedHandHtml(slapState.keptCards, slapState.discardedCard)}
      <ol class="result-order">${orderItems}</ol>

      ${room.config.customPenalties ? `<div id="penalty-area"></div>` : ""}

      <ul class="roster" style="margin-top:16px;">
        ${renderRankedRoster(players, uid)}
      </ul>

      ${isHost ? `<div class="actions"><button id="next-round">Start Next Round</button></div>` : ""}
    </div>
  `;

  const penaltyArea = root.querySelector("#penalty-area");
  if (penaltyArea) {
    if (room.round.penalty) {
      penaltyArea.innerHTML = `<div class="holder-banner">Penalty: "${escapeHtml(room.round.penalty.text)}"</div>`;
    } else if (isWinner) {
      penaltyArea.innerHTML = `
        <label for="penalty-text">Choose a penalty for the loser(s)</label>
        <input id="penalty-text" maxlength="80" placeholder="e.g. 10 push-ups" />
        <div class="actions"><button id="set-penalty">Set Penalty</button></div>
      `;
      penaltyArea.querySelector("#set-penalty").addEventListener("click", async () => {
        const text = penaltyArea.querySelector("#penalty-text").value.trim();
        if (!text) {
          ctx.showToast("Enter a penalty first.");
          return;
        }
        await ctx.call("set_penalty", { room_code: ctx.roomCode, penalty_text: text }).catch(() => {});
      });
    } else {
      penaltyArea.innerHTML = `<p class="muted">Waiting for ${escapeHtml(winner ? winner.displayName : "the winner")} to choose a penalty…</p>`;
    }
  }

  const nextBtn = root.querySelector("#next-round");
  if (nextBtn) {
    nextBtn.addEventListener("click", async () => {
      nextBtn.disabled = true;
      try {
        await ctx.call("start_next_round", { room_code: ctx.roomCode });
      } catch (_) {
        nextBtn.disabled = false;
      }
    });
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
