let activeTab = "create";
let tabExplicitlyChosen = false;

export function renderHome(root, ctx) {
  // Arriving via a shared invite link (?room=CODE): default straight to the
  // Join tab, but only until the visitor manually picks a tab themselves.
  if (!tabExplicitlyChosen && ctx.pendingJoinCode) {
    activeTab = "join";
  }

  root.innerHTML = `
    <div class="card-panel">
      <h2>Slap Four</h2>
      <p class="muted">Collect four of a kind, then be the fastest to slap the table. Whoever wins picks how many of the slowest players get penalized.</p>
      <div class="tabs">
        <button data-tab="create" class="${activeTab === "create" ? "active" : ""}">Create Room</button>
        <button data-tab="join" class="${activeTab === "join" ? "active" : ""}">Join Room</button>
      </div>
      <div id="tab-body"></div>
      <div id="home-error"></div>
    </div>
  `;

  root.querySelectorAll("[data-tab]").forEach((btn) => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab;
      tabExplicitlyChosen = true;
      renderHome(root, ctx);
    });
  });

  const body = root.querySelector("#tab-body");
  if (activeTab === "create") {
    renderCreateForm(body, ctx);
  } else {
    renderJoinForm(body, ctx);
  }
}

function renderCreateForm(body, ctx) {
  body.innerHTML = `
    <label for="create-name">Your name</label>
    <input id="create-name" maxlength="20" value="${escapeAttr(ctx.displayName)}" placeholder="e.g. Ravi" />

    <label for="create-count">Number of players</label>
    <select id="create-count">
      ${[3, 4, 5, 6, 7, 8].map((n) => `<option value="${n}">${n} players</option>`).join("")}
    </select>

    <label class="checkbox-row">
      <input type="checkbox" id="create-custom-penalties" />
      Let the winner write a custom penalty (otherwise just playing for points)
    </label>

    <div class="actions">
      <button id="create-submit">Create Room</button>
    </div>
  `;

  body.querySelector("#create-submit").addEventListener("click", async () => {
    const name = body.querySelector("#create-name").value.trim();
    const playerCount = Number(body.querySelector("#create-count").value);
    const customPenalties = body.querySelector("#create-custom-penalties").checked;
    if (!name) {
      ctx.showToast("Enter your name first.");
      return;
    }
    ctx.setDisplayName(name);
    try {
      const result = await ctx.call("create_room", {
        display_name: name,
        player_count: playerCount,
        custom_penalties: customPenalties,
      });
      ctx.setRoomCode(result.roomCode);
    } catch (_) {
      // ctx.call already toasted the error.
    }
  });
}

function renderJoinForm(body, ctx) {
  body.innerHTML = `
    <label for="join-name">Your name</label>
    <input id="join-name" maxlength="20" value="${escapeAttr(ctx.displayName)}" placeholder="e.g. Ravi" />

    <label for="join-code">Room code</label>
    <input id="join-code" maxlength="5" value="${escapeAttr(ctx.pendingJoinCode || "")}" placeholder="e.g. K7R2M" style="text-transform:uppercase" />

    <div class="actions">
      <button id="join-submit">Join Room</button>
    </div>
  `;

  body.querySelector("#join-submit").addEventListener("click", async () => {
    const name = body.querySelector("#join-name").value.trim();
    const code = body.querySelector("#join-code").value.trim().toUpperCase();
    if (!name || !code) {
      ctx.showToast("Enter your name and a room code.");
      return;
    }
    ctx.setDisplayName(name);
    try {
      const result = await ctx.call("join_room", { display_name: name, room_code: code });
      ctx.setRoomCode(result.roomCode);
    } catch (_) {
      // ctx.call already toasted the error.
    }
  });
}

function escapeAttr(value) {
  return String(value).replace(/"/g, "&quot;");
}
