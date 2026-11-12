"""Integration tests: undo and save/load working together through Session actions.

Every step goes through dispatch(), the same entry point the browser uses, and
games are written to real files in a temporary folder.
"""

from pathlib import Path
from typing import Any

from game import new_position
from session import SAVE_SUFFIX, Session

# White's e4 pawn takes Black's d5 pawn on the third move.
WITH_CAPTURE = [("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("g8", "f6")]


def fresh(save_dir: Path, opponent: str = "human") -> Session:
    session = Session(opponent)
    session.save_dir = save_dir
    return session


def play(session: Session, moves: list[tuple[str, str]]) -> None:
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def state(view: dict[str, Any]) -> dict[str, Any]:
    """What undo and load must restore, copied so later moves cannot change it."""
    return {
        "board": dict(view["board"]),
        "turn": view["turn"],
        "moves": list(view["moves"]),
        "opponent": view["opponent"],
    }


def test_undo_after_load_restores_a_capture_made_before_saving(tmp_path: Path) -> None:
    original = fresh(tmp_path)
    play(original, WITH_CAPTURE[:2])
    before_capture = state(original.view())
    play(original, WITH_CAPTURE[2:3])  # e4xd5 captures the black pawn.
    after_capture = state(original.view())
    assert after_capture["board"]["d5"] == "wP"
    play(original, WITH_CAPTURE[3:])
    original.dispatch({"action": "save", "name": "capture"})
    assert (tmp_path / ("capture" + SAVE_SUFFIX)).is_file()

    restored = fresh(tmp_path)
    restored.dispatch({"action": "load", "name": "capture"})
    view = restored.dispatch({"action": "undo"})  # Takes back g8-f6.
    assert state(view) == after_capture
    view = restored.dispatch({"action": "undo"})  # Takes back the capture.

    assert state(view) == before_capture
    assert view["board"]["d5"] == "bP"  # The captured pawn is back.
    assert view["board"]["e4"] == "wP"
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "d7-d5"]


def test_undo_before_saving_is_kept_and_undo_continues_to_the_start(tmp_path: Path) -> None:
    original = fresh(tmp_path)
    play(original, WITH_CAPTURE)
    original.dispatch({"action": "undo"})
    undone = state(original.view())
    original.dispatch({"action": "save", "name": "undone"})

    restored = fresh(tmp_path)
    view = restored.dispatch({"action": "load", "name": "undone"})
    assert state(view) == undone
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    assert view["turn"] == "b"
    assert "f6" not in view["board"]  # The undone g8-f6 did not come back.

    for remaining in (2, 1, 0):
        view = restored.dispatch({"action": "undo"})
        assert len(view["moves"]) == remaining
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["can_undo"] is False
    view = restored.dispatch({"action": "undo"})  # Nothing left: no change.
    assert view["board"] == new_position()[0]
    assert view["moves"] == []


def test_new_game_after_load_cannot_undo_into_the_loaded_game(tmp_path: Path) -> None:
    original = fresh(tmp_path)
    play(original, WITH_CAPTURE)
    original.dispatch({"action": "save", "name": "old"})

    session = fresh(tmp_path)
    session.dispatch({"action": "load", "name": "old"})
    assert session.view()["can_undo"] is True
    view = session.dispatch({"action": "new", "opponent": "human"})
    assert view["can_undo"] is False

    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["moves"] == []
    assert view["turn"] == "w"

    # A move in the new game undoes back to the new start, not to the loaded game.
    play(session, [("d2", "d4")])
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["moves"] == []
    assert session.dispatch({"action": "undo"})["moves"] == []
