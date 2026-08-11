# Slap Four

A real-time multiplayer card game (see `VIDEO_NOTES.md` for the original
rules) built on Firebase: Firestore for realtime state, Python Cloud
Functions (2nd gen) for all game logic, Anonymous Auth for room-code based
access, and a plain HTML/CSS/JS frontend (no build step).

Firebase project: **card-slap-game** (already created and linked via
`.firebaserc`).

## Project layout

- `firestore.rules` / `firestore.indexes.json` - Firestore security rules
  (hands are private to their owner; every other write goes through a
  Cloud Function).
- `functions/` - Python Cloud Functions.
  - `game/deck.py` - deck construction, dealing, seat-order helpers.
  - `game/rooms.py` - `create_room`, `join_room`, `leave_room`.
  - `game/round_flow.py` - `start_round`, `pass_card`, `start_next_round`.
  - `game/slap.py` - `slap`, `resolve_round`, `set_penalty`, and the
    scheduled `auto_resolve_stalled_rounds` backstop.
  - `main.py` - wires the above up as callable/scheduled functions.
- `public/` - static frontend served by Firebase Hosting.
  - `app.js` - top-level state machine (Firebase init, auth, Firestore
    listeners, screen switching, header Leave/Scores controls).
  - `screens/` - one module per screen (home, lobby, passing, slap, result,
    plus the persistent hand panel).

### The pressure tier is computed from the cards, never chosen freely

`functions/game/deck.py:classify_win(discarded_card, kept_4_cards)` is the
sole source of truth - the tier is fully determined by exactly which cards
are involved, not a menu the player picks from:

- **Single**: kept 4 all match, no Joker involved anywhere.
- **Super**: kept 4 = 3 matching + the Joker standing in as the wildcard 4th
  (discarding a genuine off-rank card).
- **Ultimate Super**: kept 4 are a clean natural four-of-a-kind (no Joker
  among them), achieved specifically by discarding the Joker itself - i.e.
  the player was sitting on a complete set *and* the Joker, and chose to
  shed the Joker rather than anything else.

`hand.js` mirrors this same classification purely to preview the outcome to
the player before they commit; `pass_card` recomputes it itself server-side
and ignores any client-sent tier, so a client can't claim a tier it didn't
actually earn.

**Ultimate Super Pressure never waits for a click at all.** The moment a
player's hand contains a complete natural four-of-a-kind *and* the Joker
(i.e. discarding the Joker would win Ultimate), `hand.js`'s `renderHand()`
detects this via `findUltimateDiscard()` and immediately calls `pass_card`
itself with the Joker as the discard - before rendering any cards as
clickable at all. There is no card to tap, no confirm prompt, nothing to
wait for: it fires the instant the qualifying card lands in hand. This is
deliberate - Ultimate is always the objectively best outcome for whoever
gets it (they're exempt from the penalty regardless of tier, and it
penalizes the most opponents), so there's never a reason for a human to be
in the loop for it at all.

For Single and Super, the player still gets a real choice **only when
declining is actually meaningful**: `hand.js`'s `hasEscapeCard()` checks
whether any *other* card in the current hand could be discarded without
winning anything. If a genuine non-winning alternative exists, tapping the
winning card shows "Slap now" vs. "keep playing instead" (which still
passes that exact card to the next player as a perfectly normal,
non-winning discard via `pass_card`'s `decline_win: true` flag - the relay
just continues, and the declined four-of-a-kind sits in the player's hand,
now 4 cards again, until cashed in on a future turn). In practice, "no
escape exists" and "Ultimate is achievable" turn out to be the same
condition in this game (the deck has exactly 4 copies per rank and 1
Joker, so 4-real-plus-Joker is the only 5-card shape where every possible
discard wins something) - so by the time `hasEscapeCard()` would ever
matter, the hand has already auto-resolved above and never reaches the
click handler at all.

`create_room` no longer takes a `penalty_mode` argument - there's nothing
room-wide to configure here anymore.

### The winning hand is revealed to everyone, not just claimed in text

The card discarded to win is deliberately never handed to anyone (see
above - the round ends immediately and every hand is redealt fresh next
round, so passing it on would be pointless) - but with nothing showing it
anywhere, it looked like a bug ("where did the Joker go?"), and other
players had no way to actually verify the winner's claimed combo since
hands are private during play. `pass_card` now stores both the winner's
kept 4 cards (`round.slap.keptCards`) and the discarded card
(`round.slap.discardedCard`) on the room doc - once a round is won, the
winning hand is deliberately revealed to everyone as proof, same as a real
player showing their hand when they win. `shared.js`'s `revealedHandHtml()`
renders the 4 kept cards as real card visuals plus the discarded card
dimmed and labeled "discarded", and both `slap.js` and `result.js` display
it, so anyone can visually confirm "yes, that's really four 2s and the
Joker" rather than just trusting the text.

### Custom penalties are opt-in; the game defaults to points-only

`create_room` takes an optional `custom_penalties` bool (default `False`,
surfaced as an unchecked "Let the winner write a custom penalty" checkbox on
the create-room form). When off, the round-result screen skips the
penalty-text step entirely - `set_penalty` itself rejects calls with
`FAILED_PRECONDITION` if `room.config.customPenalties` is false, so this is
enforced server-side, not just hidden in the UI. Either way, `penaltyCount`
is always tracked per player and viewable any time via the header's 🏆
Scores button - that's the actual "playing for points" mechanism.

### Starting-holder rotation

`start_next_round` computes `start_index = (new_round_number - 1) %
len(seat_order)`, so the player dealt 5 cards (and whose turn starts the
relay) advances one seat every round and cycles through everyone before
repeating - never stuck on the same person. Verified across a full
seat-cycle in `test_holder_rotation()` in the smoke test.

**Bug found in real play (2026-08-11):** round 2 deadlocked - the intended
holder had only 4 cards and couldn't pass, while whoever actually held 5
cards wasn't marked as having the turn. Root cause: `deck.py:deal()` always
dealt 5 cards to `seat_order[0]` no matter what `holder_uid` the rotation
formula computed, while `round.holderUid` was set to the *correct* rotated
seat - round 1 accidentally worked because `holder_uid == seat_order[0]`
there, masking the bug until round 2 actually rotated away from seat 0.
Fixed by having `deal()` take `holder_uid` directly and deal 5 cards to
that exact player. The original `test_holder_rotation()` didn't catch this
because its fixture (`setup_scenario`) force-writes a crafted 5-card hand
onto whoever `round.holderUid` claims to be, which incidentally papers over
a real deal/holder mismatch - added a second check reading the *naturally
dealt* hand sizes for every seat, and a browser-level check that round 2's
actual holder can really see and play 5 cards, so this class of bug can't
hide behind a too-helpful test fixture again.

### Leaving a room

`leave_room` only works during the `lobby` phase (removing a player mid-round
would break the fixed `4*N+1` deck math for that round). It renumbers the
remaining players' `seatIndex` to stay contiguous - `join_room` assigns new
seats as `len(existing_players)`, so a gap left behind by a departing player
would otherwise collide with the next joiner's assigned seat - and hands off
`hostUid` if the host leaves, deleting the room if the last player leaves.
The header's "Leave" button calls this while `status == "lobby"`; mid-round
it relabels itself "Exit" and just marks you disconnected + navigates home
locally, since there's no safe way to actually remove a seat once cards are
dealt.

## Running locally (Emulator Suite)

```bash
cd functions
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd ..
firebase emulators:start --project card-slap-game
```

This starts Auth (9099), Firestore (8080), Functions (5001), Hosting
(5050), and the Emulator UI (4000) - open **http://127.0.0.1:5050** to play
against the emulators (the frontend auto-detects `localhost` and points at
them; no other config needed). Open multiple browser tabs/profiles to
simulate multiple players.

Notes for this machine specifically:
- Port 5000 is normally taken by macOS AirPlay Receiver, so Hosting is
  configured to use **5050** instead (see `firebase.json`).
- The emulators require **Java 21+**. If your default `java` is older, run
  emulators with `JAVA_HOME=/opt/homebrew/opt/openjdk@21` prefixed (adjust
  path per `brew info openjdk@21` if it moves).
- There were two `firebase` CLIs on PATH (an old root-owned one at
  `/usr/local/bin/firebase` v13, and the current npm one at
  `/opt/homebrew/bin/firebase` v15+, which is what got used to build this).
  If `firebase --version` shows something older than 15, call
  `/opt/homebrew/bin/firebase` explicitly.

A full automated smoke test (backend via direct callable HTTP calls, plus a
3-browser Playwright run through the actual UI) was used to verify the
entire flow end to end during development; it isn't checked into this repo
since it's throwaway verification, not part of the app.

## Deploying for real

Three things need to be done once, by hand, in the Firebase console before
`firebase deploy` will work — none of this can be done from the CLI without
your interactive login:

1. **Enable Firestore** - console → Firestore Database → Create database
   (Native mode, any region).
2. **Enable Anonymous sign-in** - console → Authentication → Sign-in method
   → enable "Anonymous".
3. **Upgrade to the Blaze (pay-as-you-go) plan** - Cloud Functions requires
   it even for very low usage. Console → bottom-left "Upgrade" → attach a
   billing account. (This Google account currently has no billing account
   set up at all - `gcloud billing accounts list` returned none - so you'll
   need to add one first.)

Then:

```bash
firebase deploy --only firestore:rules,functions,hosting --project card-slap-game
```

## Known limitations (see plan for full list of decisions)

- 3-8 players per room; deck math needs exactly `4*N + 1` cards.
- No reconnect/forfeit handling beyond a best-effort `connected` presence
  flag - a disconnected player stalls the slap phase until the host can
  force-resolve (20s) or the scheduled backstop kicks in (60s).
- No abandoned-room cleanup job yet.
