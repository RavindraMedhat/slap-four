import { revealedHandHtml } from "./shared.js";

const MIN_HOST_FORCE_RESOLVE_SECONDS = 20;

const PRESSURE_LABELS = {
  single: "Single Pressure",
  super: "Super Pressure",
  ultimate_super: "Ultimate Super Pressure",
};

let tickTimer = null;

// The moment THIS browser first rendered the slap prompt for the current
// round - reaction time is measured from here, not from the server's
// startedAt (which would still bake in this client's network latency to
// receive the "now slapping" update, exactly what this is meant to avoid).
let promptShownAt = null;
let promptShownForRound = null;

export function renderSlap(root, ctx) {
  clearInterval(tickTimer);

  const { room, players, uid } = ctx;
  const slapState = room.round.slap;

  const roundKey = `${ctx.roomCode}:${room.currentRoundNumber}`;
  if (promptShownForRound !== roundKey) {
    promptShownForRound = roundKey;
    promptShownAt = Date.now();
  }
  const winner = players.find((p) => p.uid === slapState.winnerUid);
  const isWinner = uid === slapState.winnerUid;
  const alreadySlapped = Object.prototype.hasOwnProperty.call(slapState.slaps || {}, uid);

  const slappedOrder = Object.entries(slapState.slaps || {})
    .sort((a, b) => a[1] - b[1])
    .map(([slapUid], i) => {
      const p = players.find((pp) => pp.uid === slapUid);
      return `${i + 1}. ${escapeHtml(p ? p.displayName : "?")}`;
    });

  const isHost = room.hostUid === uid;
  const startedAtMs = slapState.startedAt ? slapState.startedAt.toMillis() : Date.now();

  root.innerHTML = `
    <div class="card-panel slap-screen">
      <div class="slap-title">${escapeHtml(winner ? winner.displayName : "Someone")} got four ${escapeHtml(String(slapState.winningRank))}s!</div>
      ${revealedHandHtml(slapState.keptCards, slapState.discardedCard)}
      <div class="slap-sub">
        ${PRESSURE_LABELS[slapState.pressureMode] || slapState.pressureMode} called -
        ${isWinner ? "you're safe this round." : "SLAP THE TABLE NOW!"}
      </div>
      <button id="slap-btn" class="slap-button" ${isWinner || alreadySlapped ? "disabled" : ""}>
        ${isWinner ? "SAFE" : alreadySlapped ? "SLAPPED" : "SLAP!"}
      </button>
      <div class="slap-status">
        ${slappedOrder.length ? slappedOrder.join(" · ") : "Nobody has slapped yet."}
      </div>
      ${isHost ? `<div class="actions" style="justify-content:center;"><button id="force-resolve" class="secondary" disabled>Force resolve</button></div>` : ""}
    </div>
  `;

  const btn = root.querySelector("#slap-btn");
  if (btn && !btn.disabled) {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const reactionMs = Date.now() - promptShownAt;
      try {
        await ctx.call("slap", { room_code: ctx.roomCode, reaction_ms: reactionMs });
      } catch (_) {
        btn.disabled = false;
      }
    });
  }

  const forceBtn = root.querySelector("#force-resolve");
  if (forceBtn) {
    const updateForceBtn = () => {
      const elapsed = (Date.now() - startedAtMs) / 1000;
      const ready = elapsed >= MIN_HOST_FORCE_RESOLVE_SECONDS;
      forceBtn.disabled = !ready;
      forceBtn.textContent = ready
        ? "Force resolve (someone's stalling)"
        : `Force resolve (available in ${Math.ceil(MIN_HOST_FORCE_RESOLVE_SECONDS - elapsed)}s)`;
    };
    updateForceBtn();
    tickTimer = setInterval(updateForceBtn, 1000);
    forceBtn.addEventListener("click", async () => {
      forceBtn.disabled = true;
      try {
        await ctx.call("resolve_round", { room_code: ctx.roomCode });
      } catch (_) {
        updateForceBtn();
      }
    });
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
