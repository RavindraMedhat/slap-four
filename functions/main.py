"""Cloud Functions entry point.

Each callable is implemented in game/*.py as a plain function taking a
https_fn.CallableRequest; this module just wires them up with the
@https_fn.on_call() / @scheduler_fn.on_schedule() decorators that the
Firebase Functions Python discovery scans for as top-level names.
"""

from firebase_admin import initialize_app
from firebase_functions import https_fn

from game.rooms import create_room as _create_room, join_room as _join_room, leave_room as _leave_room
from game.round_flow import (
    start_round as _start_round,
    pass_card as _pass_card,
    start_next_round as _start_next_round,
)
from game.slap import (
    slap as _slap,
    resolve_round as _resolve_round,
    set_penalty as _set_penalty,
    auto_resolve_stalled_rounds,  # noqa: F401 - already decorated, re-exported for discovery
)

initialize_app()

create_room = https_fn.on_call()(_create_room)
join_room = https_fn.on_call()(_join_room)
leave_room = https_fn.on_call()(_leave_room)
start_round = https_fn.on_call()(_start_round)
pass_card = https_fn.on_call()(_pass_card)
start_next_round = https_fn.on_call()(_start_next_round)
slap = https_fn.on_call()(_slap)
resolve_round = https_fn.on_call()(_resolve_round)
set_penalty = https_fn.on_call()(_set_penalty)
