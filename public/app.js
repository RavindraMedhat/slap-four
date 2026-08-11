import { initializeApp } from "https://www.gstatic.com/firebasejs/10.13.0/firebase-app.js";
import {
  getAuth,
  signInAnonymously,
  onAuthStateChanged,
  connectAuthEmulator,
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-auth.js";
import {
  getFirestore,
  doc,
  collection,
  onSnapshot,
  updateDoc,
  connectFirestoreEmulator,
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-firestore.js";
import {
  getFunctions,
  httpsCallable,
  connectFunctionsEmulator,
} from "https://www.gstatic.com/firebasejs/10.13.0/firebase-functions.js";

import { firebaseConfig, USE_EMULATORS } from "./firebase-config.js";
import { renderHome } from "./screens/home.js";
import { renderLobby } from "./screens/lobby.js";
import { renderPassing } from "./screens/passing.js";
import { renderSlap } from "./screens/slap.js";
import { renderResult } from "./screens/result.js";
import { renderHand } from "./screens/hand.js";
import { renderRankedRoster } from "./screens/shared.js";

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const functions = getFunctions(app);

if (USE_EMULATORS) {
  connectAuthEmulator(auth, "http://127.0.0.1:9099", { disableWarnings: true });
  connectFirestoreEmulator(db, "127.0.0.1", 8080);
  connectFunctionsEmulator(functions, "127.0.0.1", 5001);
}

const rootEl = document.getElementById("root");
const handPanelEl = document.getElementById("hand-panel");
const roomBadgeEl = document.getElementById("room-badge");
const toastEl = document.getElementById("toast");
const scoresToggleEl = document.getElementById("scores-toggle");
const scoresPanelEl = document.getElementById("scores-panel");
const scoresListEl = document.getElementById("scores-list");
const scoresCloseEl = document.getElementById("scores-close");
const leaveToggleEl = document.getElementById("leave-toggle");

const SESSION_KEY = "slapfour.roomCode";
const NAME_KEY = "slapfour.displayName";
const ROOM_URL_PARAM = "room";

function roomCodeFromUrl() {
  const code = new URLSearchParams(location.search).get(ROOM_URL_PARAM);
  return code ? code.trim().toUpperCase() : null;
}

function syncUrlWithRoom(code) {
  const url = new URL(location.href);
  if (code) {
    url.searchParams.set(ROOM_URL_PARAM, code);
  } else {
    url.searchParams.delete(ROOM_URL_PARAM);
  }
  history.replaceState(null, "", url);
}

function inviteLinkFor(code) {
  const url = new URL(location.href);
  url.search = "";
  url.searchParams.set(ROOM_URL_PARAM, code);
  return url.toString();
}

let roomUnsub = null;
let playersUnsub = null;
let handUnsub = null;
let toastTimer = null;
let scoresOpen = false;

const ctx = {
  db,
  functions,
  auth,
  uid: null,
  displayName: sessionStorage.getItem(NAME_KEY) || "",
  roomCode: sessionStorage.getItem(SESSION_KEY) || null,
  // If this tab has no active room but was opened via a shared invite link
  // (?room=CODE), the home screen pre-fills the Join form with this code
  // instead of silently auto-joining without a name.
  pendingJoinCode: sessionStorage.getItem(SESSION_KEY) ? null : roomCodeFromUrl(),
  room: null,
  players: [],
  hand: null,
  pending: false,
  inviteLinkFor,
  setDisplayName(name) {
    ctx.displayName = name;
    sessionStorage.setItem(NAME_KEY, name);
  },
  setRoomCode(code) {
    ctx.roomCode = code;
    if (code) {
      sessionStorage.setItem(SESSION_KEY, code);
    } else {
      sessionStorage.removeItem(SESSION_KEY);
    }
    syncUrlWithRoom(code);
    subscribeToRoom();
  },
  leaveRoom() {
    ctx.room = null;
    ctx.players = [];
    ctx.hand = null;
    scoresOpen = false;
    ctx.setRoomCode(null);
    render();
  },
  showToast(message) {
    toastEl.textContent = message;
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, 3500);
  },
  async call(name, data) {
    ctx.pending = true;
    try {
      const fn = httpsCallable(functions, name);
      const res = await fn(data);
      return res.data;
    } catch (err) {
      ctx.showToast(err.message || String(err));
      throw err;
    } finally {
      ctx.pending = false;
    }
  },
};

function subscribeToRoom() {
  if (roomUnsub) { roomUnsub(); roomUnsub = null; }
  if (playersUnsub) { playersUnsub(); playersUnsub = null; }
  if (handUnsub) { handUnsub(); handUnsub = null; }

  if (!ctx.roomCode) {
    render();
    return;
  }

  const roomRef = doc(db, "rooms", ctx.roomCode);
  roomUnsub = onSnapshot(roomRef, (snap) => {
    if (!snap.exists()) {
      ctx.showToast("That room no longer exists.");
      ctx.leaveRoom();
      return;
    }
    ctx.room = snap.data();
    render();
  });

  const playersRef = collection(db, "rooms", ctx.roomCode, "players");
  playersUnsub = onSnapshot(playersRef, (snap) => {
    ctx.players = snap.docs
      .map((d) => d.data())
      .sort((a, b) => a.seatIndex - b.seatIndex);
    render();
  });

  if (ctx.uid) {
    const handRef = doc(db, "rooms", ctx.roomCode, "hands", ctx.uid);
    handUnsub = onSnapshot(handRef, (snap) => {
      ctx.hand = snap.exists() ? snap.data().cards : null;
      render();
    });
  }
}

function render() {
  renderHeaderControls();

  if (!ctx.roomCode || !ctx.room) {
    roomBadgeEl.hidden = true;
    handPanelEl.hidden = true;
    renderHome(rootEl, ctx);
    return;
  }

  roomBadgeEl.hidden = false;
  roomBadgeEl.textContent = ctx.roomCode;

  switch (ctx.room.status) {
    case "lobby":
      handPanelEl.hidden = true;
      renderLobby(rootEl, ctx);
      break;
    case "passing":
      handPanelEl.hidden = false;
      renderPassing(rootEl, ctx);
      renderHand(handPanelEl, ctx);
      break;
    case "slapping":
      handPanelEl.hidden = false;
      renderSlap(rootEl, ctx);
      renderHand(handPanelEl, ctx);
      break;
    case "round_end":
      handPanelEl.hidden = false;
      renderResult(rootEl, ctx);
      renderHand(handPanelEl, ctx);
      break;
    default:
      rootEl.innerHTML = `<div class="card-panel">Unknown room state.</div>`;
  }
}

function renderHeaderControls() {
  const inRoom = Boolean(ctx.roomCode && ctx.room);
  scoresToggleEl.hidden = !inRoom;
  leaveToggleEl.hidden = !inRoom;
  leaveToggleEl.textContent = inRoom && ctx.room.status !== "lobby" ? "Exit" : "Leave";

  if (!inRoom) {
    scoresOpen = false;
    scoresPanelEl.hidden = true;
    return;
  }

  scoresPanelEl.hidden = !scoresOpen;
  if (scoresOpen) {
    scoresListEl.innerHTML = renderRankedRoster(ctx.players, ctx.uid);
  }
}

function markPresence(connected) {
  if (!ctx.uid || !ctx.roomCode) return;
  const playerRef = doc(db, "rooms", ctx.roomCode, "players", ctx.uid);
  updateDoc(playerRef, { connected }).catch(() => {});
}

document.addEventListener("visibilitychange", () => {
  markPresence(document.visibilityState === "visible");
});
window.addEventListener("beforeunload", () => markPresence(false));

scoresToggleEl.addEventListener("click", () => {
  scoresOpen = !scoresOpen;
  render();
});
scoresCloseEl.addEventListener("click", () => {
  scoresOpen = false;
  render();
});

leaveToggleEl.addEventListener("click", async () => {
  if (!ctx.roomCode) return;
  if (ctx.room && ctx.room.status === "lobby") {
    try {
      await ctx.call("leave_room", { room_code: ctx.roomCode });
    } catch (_) {
      return; // ctx.call already toasted the error; stay put.
    }
  } else {
    // Can't actually leave mid-round without corrupting the deck/relay
    // math, so just go offline and exit locally - the round continues
    // for everyone else and the presence dot shows you as disconnected.
    markPresence(false);
  }
  ctx.leaveRoom();
});

onAuthStateChanged(auth, (user) => {
  if (!user) {
    signInAnonymously(auth).catch((err) => ctx.showToast(err.message));
    return;
  }
  ctx.uid = user.uid;
  subscribeToRoom();
  markPresence(true);
});

// Keep the address bar consistent with whatever room (if any) this tab is
// already attached to, e.g. a bookmarked/reloaded page with a stale or
// missing ?room= param but a live sessionStorage reconnect.
syncUrlWithRoom(ctx.roomCode);

rootEl.innerHTML = `<div class="card-panel">Signing you in…</div>`;
