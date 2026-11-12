# Chess workshop

Python chess game (no castling, no en passant) served to a browser by `server.py`.
All rules and game state live in Python; `static/` only draws the board and sends actions.

## Commands (activate `.venv` first)

- Run: `python3 server.py`, then open http://127.0.0.1:8000
- Tests: `python -m pytest`
- Lint: `ruff check .`   Format: `ruff format .`   Types: `mypy` (configured in
  `pyproject.toml`; `tests/test_tooling.py` runs all three as part of pytest).
- Files listed under `[tool.ruff.format] exclude` keep their hand-aligned style until the
  supplied branches are merged; remove them from the list afterwards.

## Code map

- `game.py`: position = `[board, turn]`; board maps `"e4"` to pieces like `"wP"`.
- `session.py`: `Session.dispatch(action)` handles every browser action and returns `view()`.
- `Session.history`: every move since the start as `play()` keyword arguments, e.g.
  `{"source": "e2", "target": "e4"}`. Undo and save/load both rebuild positions by
  replaying it, so any new `play()` argument (e.g. promotion) must be stored there too.
- New per-game fields belong in `Session.reset()`, which New game, undo and load rely on.

## Git (lab pair work)

- `origin` = course repo (read-only, keeps `feature/` branches). `team` = shared pair repo.
- Share with `git push -u team <branch>`; get partner work with `git fetch team`.

## Rules for changes

- Every feature branch adds its own tests in `tests/`. Against the computer, undo returns
  to the player's turn. Undo at the beginning does nothing.
- Run tests, `ruff check .` and `mypy` before committing.
