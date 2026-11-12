"""Redo: restore the moves the player just undid.

Expected outcomes, decided before implementing redo on top of undo:
  R1 Redo restores exactly what the last undo removed: the same moves, including a
     capture (captured-pieces sidebar) and a promotion (the chosen piece and its
     notation, e.g. "b7xa8=N").
  R2 Several undos are redone one at a time, in order; redo with nothing to redo does
     nothing. The view reports "can_redo".
  R3 Undo -> save -> load -> redo works: the redo continuation is stored in the save
     file and checked on load like the history.
  R4 Undo, then playing any move, discards the redo continuation.
  R5 Against the computer, undo takes back the player's move and the computer's reply,
     so redo restores both. The reply is the one that was played, not a new choice, and
     it is the player's turn again afterwards.
  R6 A new game clears both undo and redo history.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from session import Session

CAPTURE = [("e2", "e4"), ("d7", "d5"), ("e4", "d5")]


def session_in(folder: Path, opponent: str = "human") -> Session:
    session = Session(opponent)
    session.save_dir = folder
    return session


def play_all(session: Session, moves: list[tuple[str, str]]) -> None:
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def act(session: Session, command: str) -> dict[str, Any]:
    return session.dispatch({"action": command})


def promoted(piece: str) -> Session:
    """A game whose last move is b7xa8, promoting to the given piece."""
    session = Session()
    session.dispatch({"action": "promotion-setup"})
    session.dispatch({"action": "move", "source": "b7", "target": "a8", "promotion": piece})
    return session


# R1: captures and promotions -------------------------------------------------------


def test_redo_restores_a_capture_and_the_captured_pieces_display() -> None:
    session = Session()
    play_all(session, CAPTURE)
    before = session.view()
    assert before["captured"] == ["bP"]

    act(session, "undo")
    assert session.view()["captured"] == []
    assert act(session, "redo") == before


@pytest.mark.parametrize("piece", list("QRBN"))
def test_redo_restores_a_promotion_with_the_chosen_piece(piece: str) -> None:
    session = promoted(piece)
    before = session.view()
    assert before["board"]["a8"] == "w" + piece

    act(session, "undo")
    assert session.view()["board"]["b7"] == "wP"
    view = act(session, "redo")
    assert view == before
    assert view["board"]["a8"] == "w" + piece
    assert view["moves"][-1].startswith("b7xa8=" + piece)
    assert "bR" in view["captured"]


def test_undo_then_redo_of_a_promotion_keeps_later_moves_replayable() -> None:
    session = promoted("N")
    session.dispatch({"action": "move", "source": "g2", "target": "h1", "promotion": "R"})
    before = session.view()
    act(session, "undo")
    act(session, "undo")
    act(session, "redo")
    assert act(session, "redo") == before


# R2: order, empty redo, can_redo ---------------------------------------------------


def test_redo_with_nothing_to_redo_does_nothing() -> None:
    session = Session()
    assert act(session, "redo") == session.view()
    assert session.view()["can_redo"] is False
    play_all(session, [("e2", "e4")])
    assert act(session, "redo")["moves"] == ["e2-e4"]
    assert session.view()["can_redo"] is False


def test_several_undos_are_redone_one_at_a_time_in_order() -> None:
    session = Session()
    play_all(session, [("e2", "e4"), ("e7", "e5"), ("g1", "f3")])
    for _ in range(3):
        act(session, "undo")
    assert session.view()["moves"] == []
    assert session.view()["can_redo"] is True

    assert act(session, "redo")["moves"] == ["e2-e4"]
    assert act(session, "redo")["moves"] == ["e2-e4", "e7-e5"]
    view = act(session, "redo")
    assert view["moves"] == ["e2-e4", "e7-e5", "g1-f3"]
    assert view["turn"] == "b"
    assert view["can_redo"] is False
    assert view["can_undo"] is True


def test_undo_and_redo_can_alternate() -> None:
    session = Session()
    play_all(session, CAPTURE)
    final = session.view()
    for _ in range(3):
        act(session, "undo")
        assert act(session, "redo") == final


# R3: save and load keep the redo continuation --------------------------------------


def test_undo_save_load_redo(tmp_path: Path) -> None:
    original = session_in(tmp_path)
    play_all(original, CAPTURE)
    final = original.view()
    act(original, "undo")
    act(original, "undo")
    original.dispatch({"action": "save", "name": "undone"})

    restored = session_in(tmp_path)
    view = restored.dispatch({"action": "load", "name": "undone"})
    assert view["moves"] == ["e2-e4"]
    assert view["can_redo"] is True
    act(restored, "redo")
    assert act(restored, "redo") == final


def test_undo_save_load_redo_keeps_a_promotion_choice(tmp_path: Path) -> None:
    original = promoted("B")
    original.save_dir = tmp_path
    final = original.view()
    act(original, "undo")
    original.dispatch({"action": "save", "name": "promotion"})

    restored = session_in(tmp_path)
    restored.dispatch({"action": "load", "name": "promotion"})
    view = act(restored, "redo")
    assert view == final
    assert view["board"]["a8"] == "wB"


def test_a_save_without_undone_moves_loads_with_nothing_to_redo(tmp_path: Path) -> None:
    original = session_in(tmp_path)
    play_all(original, CAPTURE)
    original.dispatch({"action": "save", "name": "plain"})
    restored = session_in(tmp_path)
    assert restored.dispatch({"action": "load", "name": "plain"})["can_redo"] is False


def test_loading_a_game_replaces_the_current_redo_continuation(tmp_path: Path) -> None:
    other = session_in(tmp_path)
    play_all(other, [("d2", "d4")])
    other.dispatch({"action": "save", "name": "other"})

    session = session_in(tmp_path)
    play_all(session, CAPTURE)
    act(session, "undo")
    session.dispatch({"action": "load", "name": "other"})
    assert session.view()["can_redo"] is False
    assert act(session, "redo")["moves"] == ["d2-d4"]


def test_a_save_whose_redo_continuation_is_illegal_is_refused(tmp_path: Path) -> None:
    original = session_in(tmp_path)
    play_all(original, CAPTURE)
    act(original, "undo")
    original.dispatch({"action": "save", "name": "game"})
    path = tmp_path / "game.save.json"
    data = json.loads(path.read_text())
    # The undone capture e4xd5 is only in the redo continuation (the history ends at
    # d7-d5). Turn it into a move White cannot make, wherever the file keeps it.
    changed = []

    def tamper(value: object) -> None:
        if isinstance(value, dict):
            if value.get("source") == "e4" and value.get("target") == "d5":
                value["target"] = "h5"
                changed.append(value)
            for item in value.values():
                tamper(item)
        elif isinstance(value, list):
            for item in value:
                tamper(item)

    tamper(data)
    assert len(changed) == 1, "the save file should hold the undone move once"
    path.write_text(json.dumps(data))

    session = session_in(tmp_path)
    before = session.view()
    with pytest.raises(ValueError):
        session.dispatch({"action": "load", "name": "game"})
    assert session.view() == before


# R4: a new move discards the redo continuation -------------------------------------


def test_playing_a_different_move_after_undo_discards_redo() -> None:
    session = Session()
    play_all(session, CAPTURE)
    act(session, "undo")
    play_all(session, [("b1", "c3")])
    view = session.view()
    assert view["can_redo"] is False
    assert act(session, "redo") == view
    assert view["moves"] == ["e2-e4", "d7-d5", "b1-c3"]


def test_a_new_move_discards_every_undone_move_not_just_one() -> None:
    session = Session()
    play_all(session, [("e2", "e4"), ("e7", "e5"), ("g1", "f3")])
    act(session, "undo")
    act(session, "undo")
    play_all(session, [("c7", "c5")])
    assert session.view()["can_redo"] is False
    assert act(session, "redo")["moves"] == ["e2-e4", "c7-c5"]


# R5: against the computer ----------------------------------------------------------


def computer_game(moves: list[tuple[str, str]]) -> Session:
    """Play the given white moves, each answered by the computer."""
    session = Session("computer")
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})
        session.dispatch({"action": "computer-move"})
    return session


def test_redo_against_the_computer_restores_the_move_and_the_same_reply() -> None:
    session = computer_game([("e2", "e4"), ("d2", "d4")])
    before = session.view()
    act(session, "undo")
    assert session.view()["moves"] == before["moves"][:2]
    view = act(session, "redo")
    assert view == before
    assert view["turn"] == "w"
    assert not session.computer_to_move()


def test_redo_against_the_computer_restores_whole_turns_in_order() -> None:
    session = computer_game([("e2", "e4"), ("d2", "d4"), ("g1", "f3")])
    before = session.view()
    for _ in range(3):
        act(session, "undo")
    assert session.view()["moves"] == []
    assert act(session, "redo")["moves"] == before["moves"][:2]
    assert act(session, "redo")["moves"] == before["moves"][:4]
    assert act(session, "redo") == before


def test_redo_against_the_computer_does_not_ask_the_computer_again(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = computer_game([("e2", "e4")])
    before = session.view()
    act(session, "undo")

    def no_computer(position: object) -> None:
        raise AssertionError("redo must replay the recorded reply")

    monkeypatch.setattr("session.choose_move", no_computer)
    assert act(session, "redo") == before


def test_player_move_after_undo_against_the_computer_discards_redo() -> None:
    session = computer_game([("e2", "e4")])
    act(session, "undo")
    play_all(session, [("d2", "d4")])
    assert session.view()["can_redo"] is False
    assert session.computer_to_move()


# R6: new game ----------------------------------------------------------------------


@pytest.mark.parametrize("opponent", ["human", "computer"])
def test_new_game_clears_undo_and_redo(opponent: str) -> None:
    session = Session()
    play_all(session, CAPTURE)
    act(session, "undo")
    assert session.view()["can_redo"] is True

    view = session.dispatch({"action": "new", "opponent": opponent})
    assert view["can_undo"] is False
    assert view["can_redo"] is False
    assert act(session, "redo") == view
    assert act(session, "undo") == view
    assert view["moves"] == []
