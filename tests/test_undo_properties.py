"""Property-based tests for undo: rules that must hold for any legal game.

Hypothesis plays random legal games (choosing among the legal moves at each step)
instead of the few hand-picked games in test_undo.py.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from computer import candidate_moves
from game import new_position
from session import Session

# Each game replays every move on undo, so keep the games short and few.
FAST = settings(max_examples=30, deadline=None)


@st.composite
def games(draw, max_moves=10):
    """A Session after a random sequence of legal moves, and the views seen."""
    session = Session()
    views = [snapshot(session)]
    for _ in range(draw(st.integers(0, max_moves))):
        moves = list(candidate_moves(session.position))
        if not moves:  # Checkmate or stalemate.
            break
        session.play(*draw(st.sampled_from(moves)))
        views.append(snapshot(session))
    return session, views


def snapshot(session):
    """The parts of the view that undo must restore, copied."""
    view = session.view()
    return {
        "board": dict(view["board"]),
        "turn": view["turn"],
        "moves": list(view["moves"]),
        "status": view["status"],
        "winner": view["winner"],
    }


@FAST
@given(games())
def test_each_undo_restores_the_view_before_that_move(game):
    session, views = game
    for expected in reversed(views[:-1]):
        session.undo()
        assert snapshot(session) == expected


@FAST
@given(games())
def test_undo_all_the_way_back_reaches_the_start_and_stops(game):
    session, views = game
    for _ in range(len(views) + 2):  # Two extra undos at the beginning.
        session.undo()
    assert session.view()["board"] == new_position()[0]
    assert session.view()["moves"] == []
    assert session.view()["can_undo"] is False


@FAST
@given(games())
def test_replaying_an_undone_move_gives_the_same_game(game):
    session, views = game
    if not session.history:
        return
    last = session.history[-1]
    before = snapshot(session)
    session.undo()
    session.play(**last)
    assert snapshot(session) == before
