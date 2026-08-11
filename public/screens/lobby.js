export function renderLobby(root, ctx) {
  const { room, players, uid } = ctx;
  const isHost = room.hostUid === uid;
  const needed = room.config.playerCount;
  const canStart = players.length === needed;

  const inviteLink = ctx.inviteLinkFor(ctx.roomCode);

  root.innerHTML = `
    <div class="card-panel">
      <h2>Waiting Room</h2>
      <p class="muted">
        Share the room code above, or send an invite link. Needs exactly <strong>${needed}</strong> players.
        The pressure level (how many of the slowest slappers get penalized) is decided by which cards complete the win.
        ${room.config.customPenalties ? "The winner also gets to write a custom penalty." : "Playing for points only."}
      </p>
      <label for="invite-link">Invite link</label>
      <div class="invite-row">
        <input id="invite-link" readonly value="${escapeHtml(inviteLink)}" />
        <button id="copy-link" class="secondary">Copy</button>
      </div>
      <ul class="roster">
        ${players
          .map(
            (p) => `
          <li>
            <span>
              <span class="dot ${p.connected ? "online" : "offline"}"></span>
              ${escapeHtml(p.displayName)}
              ${p.uid === uid ? '<span class="you-tag">(you)</span>' : ""}
              ${p.isHost ? '<span class="host-tag">host</span>' : ""}
            </span>
          </li>`
          )
          .join("")}
      </ul>
      <div class="actions">
        ${
          isHost
            ? `<button id="start-round" ${canStart ? "" : "disabled"}>
                 ${canStart ? "Start Game" : `Waiting for ${needed - players.length} more player(s)…`}
               </button>`
            : `<p class="muted">Waiting for the host to start the game…</p>`
        }
      </div>
    </div>
  `;

  const startBtn = root.querySelector("#start-round");
  if (startBtn) {
    startBtn.addEventListener("click", async () => {
      startBtn.disabled = true;
      try {
        await ctx.call("start_round", { room_code: ctx.roomCode });
      } catch (_) {
        startBtn.disabled = !canStart;
      }
    });
  }

  root.querySelector("#copy-link").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(inviteLink);
      ctx.showToast("Invite link copied!");
    } catch (_) {
      root.querySelector("#invite-link").select();
      ctx.showToast("Couldn't auto-copy - link is selected, press Ctrl/Cmd+C.");
    }
  });
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}
