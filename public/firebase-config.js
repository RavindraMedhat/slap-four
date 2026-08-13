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

// This app is only ever served by the local Firebase Hosting emulator (port
// 5050, see firebase.json) - checking the port instead of the hostname means
// this still resolves correctly when another device on the same WiFi loads
// the page via this machine's LAN IP instead of localhost/127.0.0.1.
export const USE_EMULATORS = location.port === "5050";
