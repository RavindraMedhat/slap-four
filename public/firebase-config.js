// Public, safe-to-expose Firebase Web SDK config (not a secret - see
// https://firebase.google.com/docs/projects/api-keys).
export const firebaseConfig = {
  projectId: "card-slap-game",
  appId: "1:690743803368:web:1036471a93143226b3785d",
  storageBucket: "card-slap-game.firebasestorage.app",
  apiKey: "AIzaSyAUYzD2DMG1ueCPs-O5VQftJK54AGN1_NA",
  authDomain: "card-slap-game.firebaseapp.com",
  messagingSenderId: "690743803368",
};

// When served from localhost, point the SDK at the local Emulator Suite
// instead of live Firebase (see firebase.json for the matching ports).
export const USE_EMULATORS = location.hostname === "localhost" || location.hostname === "127.0.0.1";
