"""Integration tests: opponent mode and full game state across save, load and undo.

Every step goes through dispatch(), the same entry point the browser uses, and
games are written to real files in a temporary folder. The computer's replies
are random among equally good moves, so tests record them instead of assuming them.
"""

from pathlib import Path
from typing import Any

import pytest

from game import new_position
from session import Session


def fresh(save_dir: Path, opponent: str = "human") -> Session:
    session = Session(opponent)
    session.save_dir = save_dir
    return session


def move(session: Session, source: str, target: str) -> dict[str, Any]:
    return session.dispatch({"action": "move", "source": source, "target": target})


def state(view: dict[str, Any]) -> dict[str, Any]:
    """Board, side to move, notation and opponent, copied."""
    return {
        "board": dict(view["board"]),
        "turn": view["turn"],
        "moves": list(view["moves"]),
        "opponent": view["opponent"],
    }


def test_computer_game_keeps_its_mode_and_undo_takes_back_reply_and_move(tmp_path: Path) -> None:
    original = fresh(tmp_path, "computer")
    move(original, "e2", "e4")
    after_first_round = state(original.dispatch({"action": "computer-move"}))
    move(original, "d2", "d4")
    original.dispatch({"action": "computer-move"})
    saved = state(original.view())
    original.dispatch({"action": "save", "name": "vs-computer"})

    restored = fresh(tmp_path)  # Starts as a two-player game.
    view = restored.dispatch({"action": "load", "name": "vs-computer"})
    assert view["opponent"] == "computer"
    assert state(view) == saved
    assert len(view["moves"]) == 4

    # One undo removes the computer's reply and the player's d2-d4.
    view = restored.dispatch({"action": "undo"})
    assert state(view) == after_first_round
    assert view["turn"] == "w"
    view = restored.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["moves"] == []
    assert view["turn"] == "w"

    # Still against the computer: Black's moves are the computer's, not the player's.
    move(restored, "c2", "c4")
    with pytest.raises(ValueError):
        move(restored, "e7", "e5")
    view = restored.dispatch({"action": "computer-move"})
    assert view["turn"] == "w"
    assert view["moves"][0] == "c2-c4"
    assert len(view["moves"]) == 2


def test_computer_game_saved_before_the_reply_lets_the_computer_answer(tmp_path: Path) -> None:
    original = fresh(tmp_path, "computer")
    move(original, "e2", "e4")  # Saved while the computer is to move.
    original.dispatch({"action": "save", "name": "waiting"})

    restored = fresh(tmp_path)
    view = restored.dispatch({"action": "load", "name": "waiting"})
    assert view["opponent"] == "computer" and view["turn"] == "b"
    view = restored.dispatch({"action": "undo"})  # Only the player's move to take back.
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"


def test_full_lifecycle_save_load_play_then_undo_to_the_start(tmp_path: Path) -> None:
    opening = [("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6")]
    original = fresh(tmp_path)
    states = [state(original.view())]
    for source, target in opening:
        states.append(state(move(original, source, target)))
    original.dispatch({"action": "save", "name": "lifecycle"})

    restored = fresh(tmp_path)
    restored.dispatch({"action": "load", "name": "lifecycle"})
    view = move(restored, "f1", "c4")  # A move played after loading.
    assert view["moves"][-1] == "f1-c4"
    assert view["turn"] == "b"

    view = restored.dispatch({"action": "undo"})
    assert state(view) == states[-1]  # Back to the loaded position.
    for expected in reversed(states[:-1]):
        view = restored.dispatch({"action": "undo"})
        assert state(view) == expected
    assert view["board"] == new_position()[0]
    assert view["can_undo"] is False

    for _ in range(3):  # Undo at the start does nothing.
        view = restored.dispatch({"action": "undo"})
        assert state(view) == states[0]


@pytest.mark.parametrize(
    "moves",
    [
        [],  # Starting position.
        [("e2", "e4")],  # Black to move.
        [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5")],  # Two captures.
        [("e2", "e4"), ("d7", "d5"), ("f1", "b5")],  # Check.
        [("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")],  # Checkmate.
    ],
    ids=["start", "black-to-move", "captures", "check", "checkmate"],
)
def test_load_restores_exactly_the_state_before_saving(
    tmp_path: Path, moves: list[tuple[str, str]]
) -> None:
    original = fresh(tmp_path)
    for source, target in moves:
        move(original, source, target)
    before = original.view()
    original.dispatch({"action": "save", "name": "exact"})

    restored = fresh(tmp_path)
    after = restored.dispatch({"action": "load", "name": "exact"})

    assert after["board"] == before["board"]
    assert after["turn"] == before["turn"]
    assert after["moves"] == before["moves"]
    assert len(after["moves"]) == len(moves)  # Every move, none lost or added.
    assert after["status"] == before["status"]
    assert after["winner"] == before["winner"]
    assert after == before  # Nothing else in the view differs either.


def test_check_and_checkmate_cases_are_what_they_claim() -> None:
    for moves, expected in [
        ([("e2", "e4"), ("d7", "d5"), ("f1", "b5")], "check"),
        ([("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")], "checkmate"),
    ]:
        session = Session()
        for source, target in moves:
            move(session, source, target)
        assert session.view()["status"] == expected
