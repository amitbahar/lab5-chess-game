# Chess workshop

A local chess game in Python, for two players or against the computer. Requires Python 3.10
or later. Ask your coding agent to create `.venv` and install `requirements-dev.txt` in it.
Activate the environment in each terminal you use:

```sh
source .venv/bin/activate
```

```sh
python3 server.py
# Open http://127.0.0.1:8000
python -m pytest
```

Start a game against another person or against the computer. Against the computer you
play White; it looks one move ahead and plays the move that leaves it the most material,
preferring checkmate. Select a piece, then a highlighted destination. White moves first.
Standard movement, captures, check, checkmate and stalemate apply: you cannot leave your
own king in check, checkmate wins, and stalemate is a draw. Pawns initially remain pawns at
the far rank; a later branch adds promotion to a piece the player chooses. There is no clock.

**Not supported: castling and en passant.** Neither move exists in this game. The other
draw rules (insufficient material, threefold repetition, the fifty-move rule) are not
implemented either.

To reach promotion quickly from a new game, play a2-a4, h7-h5, a4-a5, h5-h4, a5-a6,
h4-h3, a6-b7, h3-g2. White can then play b7 to a8. In tests, the `promotion-setup` action
plays the same moves.

## Saving and loading

Type a name (letters, digits, `-` and `_`) and press **Save** to write the game to
`<name>.save.json` beside `server.py`, or in the folder given with `--save-dir`. Saving over an
existing name asks first. **Load** restores the board, turn, moves, opponent and the move
history used to undo, even after restarting the server. A file that does not match its own
move history is refused, and the current game is kept.

## Checks

`python -m pytest` also runs `ruff check`, `ruff format --check` and `mypy`. To fix style
issues, run `ruff check --fix .` and `ruff format .`. Files shared with the other branches are
left out of formatting until they are merged (see `pyproject.toml`).

## Files

- `game.py`: board and turn in a position list; movement, check, checkmate and stalemate.
- `session.py`: game actions, the opponent, displayed move notation, and sidebar information.
- `computer.py`: the computer opponent.
- `server.py`: one in-memory game, HTTP actions, and static files. Restarting loses the game.
- `static/`: browser presentation and square selection. All movement decisions run in Python.
- `tests/`: starter behavior checks.

## Working together

Start your two branches from `main`. One partner implements save/load; the other implements
undo. Merge both into `main`, then merge the supplied `feature/captured-pieces` and
`feature/promotion` branches into `main` in that order. After each merge, run the existing
tests and try the combined game before asking your agent to repair anything. Add checks
for the behavior you establish. Implement redo together using the undo mechanism you created.

Save/load must restore the game in a fresh instance, including whether the opponent is a
person or the computer, and preserve enough information to undo moves made before saving.
Undo must restore captured pieces and the side to move; decide together what it does
against the computer. Undo at the beginning does nothing. Move notation should describe the
currently played continuation. New game clears the previous game.

The captured-pieces display shows pieces actually captured, with their type at capture.
Promotion alone is not a capture. Undoing a capture removes it from the display.

Redo restores the undone move, including capture and promotion; against the computer,
decide what it restores. A different move after undo discards redo. For this workshop,
save/load should also preserve the ability to redo.

Establish checks for interactions as you integrate features. Supplied branches are workshop
contributions to inspect and integrate, not a guarantee of correctness in every combination.
