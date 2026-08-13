# Slap Four - local LAN setup

This is a real-time multiplayer card game. This laptop should run it locally
via the Firebase Emulator Suite (no cloud project, no billing, no internet
dependency beyond the initial `npm`/`pip`/`brew` installs). Other players on
the same WiFi connect to this machine's local IP in their browser.

Do the following, in order, and fix anything that fails before moving on -
don't skip steps or assume something is already installed.

## 1. Get the code

If this directory isn't already the cloned repo:

```bash
git clone https://github.com/RavindraMedhat/slap-four.git
cd slap-four
```

Check out the branch with the LAN-play fixes:

```bash
git checkout lan-play
```

## 2. Python environment for Cloud Functions

```bash
cd functions
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

Verify it worked:

```bash
functions/venv/bin/python3 -c "import firebase_functions, firebase_admin; print('deps OK')"
```

## 3. Install Firebase CLI and Java

```bash
npm install -g firebase-tools
brew install openjdk@21
```

**Important (macOS):** confirm `firebase` resolves to the npm-installed,
architecture-native binary, not some other pre-existing standalone install:

```bash
which firebase
file "$(which firebase)"
```

If `file` reports the wrong architecture for this Mac (e.g. x86_64 on Apple
Silicon), the Cloud Functions emulator will crash with an `ImportError:
... incompatible architecture` error when it spawns Python. Fix by using the
npm-installed CLI explicitly instead of whatever `which firebase` found:

```bash
node -p "require('path').dirname(require.resolve('firebase-tools/package.json'))"
# then run the emulator via that package's lib/bin/firebase.js instead of
# the shadowing binary - or just remove/rename the conflicting old binary at
# whatever path `which firebase` printed.
```

## 4. Start the emulators

From the repo root, with the functions venv active:

```bash
export PATH="$(brew --prefix openjdk@21)/bin:$PATH"
firebase emulators:start --only auth,firestore,functions,hosting
```

Wait for all four to report ready:
- `Local server: http://0.0.0.0:5050` (Hosting)
- Firestore Emulator started
- Auth emulator listening on `0.0.0.0:9099`
- Functions emulator watching for changes

If the Firestore emulator errors about needing Java 21+, re-check step 3 and
make sure the `export PATH=...` line above actually put `openjdk@21` ahead of
any older Java on PATH (`java -version` should print 21.x after that export).

## 5. Get this machine's LAN IP and share it

```bash
ipconfig getifaddr en0
```

Give other players `http://<that-ip>:5050` to open in their own browser -
they must be on the same WiFi network as this machine.

## 6. macOS Firewall (only if other devices can't connect)

If the page loads for other players but creating/joining a room fails or a
room mysteriously "no longer exists" seconds after creating it, the Firestore
emulator's real-time sync is being blocked by the macOS Application
Firewall. Fix:

```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --listapps | grep -A1 java
```

If it shows "(Block incoming connections)" for the `java` binary used by
step 3/4, either:
- **System Settings → Network → Firewall → Options...** → find `java` →
  change to **"Allow incoming connections"**, or
- run (needs the machine's admin password):

```bash
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp "<path to that java binary>"
```

## Verify it's actually working

Don't declare this done from reading code - launch it and drive it:

1. Open `http://localhost:5050` in a browser on this machine.
2. Create a room, confirm the lobby shows a room code and you as host.
3. From a second browser tab/window, join with that room code, confirm both
   tabs show each other in the roster in real time (no reload needed).
4. Only after that works locally, test from an actual second device on the
   WiFi using the LAN IP from step 5.
