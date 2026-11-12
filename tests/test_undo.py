"""Unit tests for undo, one per requirement in the lab instructions.

Stories (from the README and lab text):
  S1 "a control that lets the player reverse the last move"
  S2 "Undo must restore captured pieces and the side to move"
  S3 "Undo at the beginning does nothing"
  S4 "decide together what it does against the computer"
     -> we decided: undo returns to the player's turn (removes the reply too)
  S5 "Move notation should describe the currently played continuation"
  S6 "New game clears the previous game"
"""

import pytest

from game import new_position
from session import Session


def test_undo_at_the_beginning_does_nothing() -> None:
    # Story S3
    session = Session()
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["can_undo"] is False


def test_undo_reverses_the_last_move_and_side_to_move() -> None:
    # Story S1, S2
    session = Session()
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    assert session.view()["can_undo"] is True
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["can_undo"] is False


def test_undo_restores_a_captured_piece() -> None:
    # Story S2, S5
    session = Session()
    for source, target in [("e2", "e4"), ("d7", "d5"), ("e4", "d5")]:
        session.play(source, target)
    session.undo()
    view = session.view()
    assert view["board"]["d5"] == "bP"
    assert view["board"]["e4"] == "wP"
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "d7-d5"]


def test_repeated_undo_goes_back_one_move_at_a_time() -> None:
    # Story S1, S3, S5
    session = Session()
    for source, target in [("e2", "e4"), ("e7", "e5"), ("g1", "f3")]:
        session.play(source, target)
    session.undo()
    assert session.view()["moves"] == ["e2-e4", "e7-e5"]
    assert session.view()["turn"] == "w"
    session.undo()
    assert session.view()["moves"] == ["e2-e4"]
    assert session.view()["turn"] == "b"
    session.undo()
    session.undo()  # Extra undo at the beginning does nothing.
    assert session.view()["board"] == new_position()[0]
    assert session.view()["moves"] == []


def test_a_new_move_after_undo_continues_from_there() -> None:
    # Story S5
    session = Session()
    session.play("e2", "e4")
    session.undo()
    session.play("d2", "d4")
    view = session.view()
    assert view["moves"] == ["d2-d4"]
    assert "e4" not in view["board"]
    assert view["board"]["d4"] == "wP"


def test_undo_leaves_checkmate() -> None:
    # Story S1, S2
    session = Session()
    for source, target in [("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")]:
        session.play(source, target)
    assert session.view()["status"] == "checkmate"
    session.undo()
    view = session.view()
    assert view["status"] is None
    assert view["winner"] is None
    assert view["turn"] == "b"
    assert view["board"]["d8"] == "bQ"


def test_undo_against_the_computer_returns_to_the_players_turn() -> None:
    # Story S4
    session = Session("computer")
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    session.dispatch({"action": "computer-move"})
    assert len(session.view()["moves"]) == 2
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    assert view["moves"] == []
    assert view["opponent"] == "computer"
    # The player can move again, and the computer still answers.
    session.dispatch({"action": "move", "source": "d2", "target": "d4"})
    view = session.dispatch({"action": "computer-move"})
    assert view["turn"] == "w"
    assert view["moves"][0] == "d2-d4"


def test_undo_against_the_computer_before_its_reply() -> None:
    # Story S4
    session = Session("computer")
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["turn"] == "w"
    with pytest.raises(ValueError):
        session.dispatch({"action": "computer-move"})


def test_new_game_clears_undo_history() -> None:
    # Story S6
    session = Session()
    session.play("e2", "e4")
    session.dispatch({"action": "new"})
    view = session.dispatch({"action": "undo"})
    assert view["board"] == new_position()[0]
    assert view["can_undo"] is False
