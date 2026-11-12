"""Integration tests: promotion together with undo, save/load and captured pieces.

The history that undo and load replay must include the promoted piece.
"""

from pathlib import Path
from typing import Any

from session import Session

# After promotion-setup, White plays b7xa8 and Black plays g2xh1; both promote.


def setup(save_dir: Path | None = None) -> Session:
    session = Session()
    if save_dir is not None:
        session.save_dir = save_dir
    session.dispatch({"action": "promotion-setup"})
    return session


def promote(session: Session, source: str, target: str, piece: str) -> dict[str, Any]:
    return session.dispatch(
        {"action": "move", "source": source, "target": target, "promotion": piece}
    )


def test_undo_takes_back_a_promotion_and_its_capture() -> None:
    session = setup()
    before_moves = list(session.view()["moves"])
    before_captured = list(session.view().get("captured", []))
    promote(session, "b7", "a8", "N")
    view = session.dispatch({"action": "undo"})
    assert view["board"]["b7"] == "wP"
    assert view["board"]["a8"] == "bR"  # The captured rook is back.
    assert view["turn"] == "w"
    assert view["moves"] == before_moves
    assert view.get("captured", []) == before_captured


def test_undo_keeps_an_earlier_promotion_as_the_chosen_piece() -> None:
    session = setup()
    promote(session, "b7", "a8", "N")
    promote(session, "g2", "h1", "Q")
    view = session.dispatch({"action": "undo"})
    assert view["board"]["a8"] == "wN"  # Still the knight White chose.
    assert view["board"]["g2"] == "bP"
    assert view["moves"][-1] == "b7xa8=N"
    assert view["turn"] == "b"


def test_save_and_load_a_game_with_promotions_then_undo(tmp_path: Path) -> None:
    original = setup(tmp_path)
    promote(original, "b7", "a8", "R")
    promote(original, "g2", "h1", "B")
    saved = original.view()
    original.dispatch({"action": "save", "name": "promoted"})

    restored = Session()
    restored.save_dir = tmp_path
    view = restored.dispatch({"action": "load", "name": "promoted"})
    assert view == saved
    assert view["board"]["a8"] == "wR" and view["board"]["h1"] == "bB"

    view = restored.dispatch({"action": "undo"})
    assert view["board"]["g2"] == "bP"
    assert view["board"]["h1"] == "wR"  # White's captured rook is back.
    assert view["board"]["a8"] == "wR"


def test_load_rejects_a_saved_promotion_to_a_king(tmp_path: Path) -> None:
    original = setup(tmp_path)
    promote(original, "b7", "a8", "Q")
    original.dispatch({"action": "save", "name": "bad"})
    path = tmp_path / "bad.save.json"
    path.write_text(path.read_text().replace('"promotion": "Q"', '"promotion": "K"'))

    restored = Session()
    restored.save_dir = tmp_path
    try:
        restored.dispatch({"action": "load", "name": "bad"})
    except ValueError:
        pass
    else:
        raise AssertionError("Loading a promotion to a king must fail")
    assert restored.view()["moves"] == []  # The current game is unchanged.
