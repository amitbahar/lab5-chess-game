"""Interaction tests: undo together with save/load (lab: "Save/load must ...
preserve enough information to undo moves made before saving")."""

from pathlib import Path

from session import Session


def session_in(folder: Path, opponent: str = "human") -> Session:
    session = Session(opponent)
    session.save_dir = folder
    return session


def test_undo_after_load_takes_back_a_move_made_before_saving(tmp_path: Path) -> None:
    original = session_in(tmp_path)
    for source, target in [("e2", "e4"), ("d7", "d5"), ("e4", "d5")]:
        original.play(source, target)
    original.save("capture")
    restored = session_in(tmp_path)
    restored.load("capture")
    restored.undo()
    view = restored.view()
    assert view["board"]["d5"] == "bP" and view["board"]["e4"] == "wP"
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert view["turn"] == "w"


def test_undo_after_loading_a_computer_game_returns_to_the_player(tmp_path: Path) -> None:
    original = session_in(tmp_path, "computer")
    original.dispatch({"action": "move", "source": "e2", "target": "e4"})
    original.dispatch({"action": "computer-move"})
    original.save("vs-computer")
    restored = session_in(tmp_path)
    restored.load("vs-computer")
    restored.undo()
    assert restored.view()["opponent"] == "computer"
    assert restored.view()["moves"] == []
    assert restored.view()["turn"] == "w"


def test_saving_after_undo_saves_the_undone_game(tmp_path: Path) -> None:
    original = session_in(tmp_path)
    original.play("e2", "e4")
    original.play("e7", "e5")
    original.undo()
    original.save("after-undo")
    restored = session_in(tmp_path)
    restored.load("after-undo")
    assert restored.view()["moves"] == ["e2-e4"]
    assert restored.view()["turn"] == "b"
