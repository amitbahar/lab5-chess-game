"""Save a game to a file and resume it in a fresh instance."""

import json
import os
import threading
import urllib.request

import pytest

from game import new_position
from server import make_server
from session import Session

OPENING = [("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6"), ("f1", "c4")]


def fresh(save_dir, opponent="human"):
    session = Session(opponent)
    session.save_dir = save_dir
    return session


def play_all(session, moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def test_round_trip_preserves_board_turn_notation_and_opponent(tmp_path):
    original = fresh(tmp_path)
    play_all(original, OPENING)
    original.dispatch({"action": "save", "name": "opening"})

    restored = fresh(tmp_path)
    view = restored.dispatch({"action": "load", "name": "opening"})

    assert view == original.view()
    assert restored.position == original.position
    assert restored.position[1] == "b"
    assert restored.notation == ["e2-e4", "e7-e5", "g1-f3", "b8-c6", "f1-c4"]
    assert restored.opponent == "human"


def test_history_is_kept_for_undoing_moves_made_before_saving(tmp_path):
    original = fresh(tmp_path)
    play_all(original, OPENING)
    original.dispatch({"action": "save", "name": "opening"})

    restored = fresh(tmp_path)
    restored.dispatch({"action": "load", "name": "opening"})

    assert restored.history == [{"source": s, "target": t} for s, t in OPENING]
    # Replaying all but the last move rebuilds the position before it, which is
    # what undoing an earlier move needs.
    earlier = Session()
    play_all(earlier, OPENING[:-1])
    replayed = Session()
    for step in restored.history[:-1]:
        replayed.play(step["source"], step["target"])
    assert replayed.position == earlier.position
    assert replayed.notation == restored.notation[:-1]


def test_play_after_loading_continues_the_game(tmp_path):
    original = fresh(tmp_path)
    play_all(original, OPENING)
    original.dispatch({"action": "save", "name": "opening"})

    restored = fresh(tmp_path)
    restored.dispatch({"action": "load", "name": "opening"})
    play_all(restored, [("g8", "f6")])
    assert restored.notation[-1] == "g8-f6"
    assert len(restored.history) == len(OPENING) + 1


def test_computer_opponent_is_restored(tmp_path):
    original = fresh(tmp_path, "computer")
    play_all(original, [("e2", "e4")])
    original.dispatch({"action": "computer-move"})
    play_all(original, [("d2", "d4")])
    original.dispatch({"action": "save", "name": "versus"})

    restored = fresh(tmp_path)
    view = restored.dispatch({"action": "load", "name": "versus"})
    assert view["opponent"] == "computer"
    assert restored.computer_to_move()
    restored.dispatch({"action": "computer-move"})
    assert len(restored.notation) == 4


def test_finished_game_is_restored_as_finished(tmp_path):
    original = fresh(tmp_path)
    play_all(original, [("f2", "f3"), ("e7", "e5"), ("g2", "g4"), ("d8", "h4")])
    assert original.view()["status"] == "checkmate"
    original.dispatch({"action": "save", "name": "mate"})

    restored = fresh(tmp_path)
    view = restored.dispatch({"action": "load", "name": "mate"})
    assert view["status"] == "checkmate"
    assert view["winner"] == "Black"
    assert view["moves"][-1] == "d8-h4#"


def test_save_writes_a_readable_file(tmp_path):
    session = fresh(tmp_path)
    play_all(session, [("e2", "e4")])
    view = session.dispatch({"action": "save", "name": "my-game_1"})
    assert view["moves"] == ["e2-e4"]

    data = json.loads((tmp_path / "my-game_1.save.json").read_text())
    assert data["opponent"] == "human"
    assert data["turn"] == "b"
    assert data["board"]["e4"] == "wP"
    assert data["moves"] == ["e2-e4"]
    assert data["history"] == [{"source": "e2", "target": "e4"}]


def test_new_game_and_promotion_setup_reset_history(tmp_path):
    session = fresh(tmp_path)
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "new"})
    assert session.history == []
    assert session.save_dir == tmp_path
    session.dispatch({"action": "promotion-setup"})
    assert len(session.history) == 8


@pytest.mark.parametrize("name", ["", None, "../escape", "a/b", "dot.name", " ", 7])
def test_unsafe_or_missing_names_are_refused(tmp_path, name):
    session = fresh(tmp_path)
    with pytest.raises(ValueError):
        session.dispatch({"action": "save", "name": name})
    with pytest.raises(ValueError):
        session.dispatch({"action": "load", "name": name})
    assert list(tmp_path.iterdir()) == []


def test_loading_a_missing_file_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        fresh(tmp_path).dispatch({"action": "load", "name": "nothing"})


def corrupt(tmp_path, change):
    original = fresh(tmp_path)
    play_all(original, OPENING)
    original.dispatch({"action": "save", "name": "game"})
    path = tmp_path / "game.save.json"
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


@pytest.mark.parametrize(
    "change",
    [
        lambda d: d["board"].update({"e4": "bQ"}),  # board disagrees with history
        lambda d: d.update(turn="w"),  # turn disagrees with history
        lambda d: d["moves"].pop(),  # notation disagrees with history
        lambda d: d.update(opponent="alien"),  # unknown opponent
        lambda d: d["history"].append({"source": "e1", "target": "e5"}),  # illegal move
        lambda d: d["history"].append({"source": "e1"}),  # malformed step
        lambda d: d.update(history="e2-e4"),  # wrong type
        lambda d: d.update(version=999),  # unknown format version
        lambda d: d.pop("board"),  # missing field
    ],
)
def test_inconsistent_files_are_refused_and_leave_the_game_unchanged(tmp_path, change):
    corrupt(tmp_path, change)
    session = fresh(tmp_path)
    play_all(session, [("d2", "d4")])
    before = session.view(), list(session.history)
    with pytest.raises(ValueError):
        session.dispatch({"action": "load", "name": "game"})
    assert (session.view(), session.history) == before


def test_non_json_file_is_refused(tmp_path):
    (tmp_path / "junk.save.json").write_text("not json {")
    with pytest.raises(ValueError):
        fresh(tmp_path).dispatch({"action": "load", "name": "junk"})


def call(server, action):
    request = urllib.request.Request(
        f"http://127.0.0.1:{server.server_port}/api/action",
        data=json.dumps(action).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def running(save_dir):
    server = make_server(0, save_dir=save_dir)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def test_a_fresh_server_resumes_a_saved_game(tmp_path):
    first = running(tmp_path)
    try:
        call(first, {"action": "new", "opponent": "computer"})
        call(first, {"action": "move", "source": "e2", "target": "e4"})
        call(first, {"action": "computer-move"})
        saved = call(first, {"action": "save", "name": "resume"})
    finally:
        first.shutdown()
        first.server_close()

    second = running(tmp_path)
    try:
        assert call(second, {"action": "load", "name": "resume"}) == saved
        assert saved["opponent"] == "computer"
        assert len(saved["moves"]) == 2
        assert saved["board"] != new_position()[0]
    finally:
        second.shutdown()
        second.server_close()


# --- Edge cases found in review -------------------------------------------------


def test_saving_over_an_existing_game_needs_confirmation(tmp_path):
    session = fresh(tmp_path)
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "save", "name": "slot"})
    play_all(session, [("e7", "e5")])
    with pytest.raises(ValueError, match="already exists"):
        session.dispatch({"action": "save", "name": "slot"})
    assert json.loads((tmp_path / "slot.save.json").read_text())["moves"] == ["e2-e4"]

    session.dispatch({"action": "save", "name": "slot", "overwrite": True})
    assert json.loads((tmp_path / "slot.save.json").read_text())["moves"] == ["e2-e4", "e7-e5"]


def test_a_failed_save_keeps_the_previous_file(tmp_path, monkeypatch):
    session = fresh(tmp_path)
    session.dispatch({"action": "save", "name": "slot"})
    before = (tmp_path / "slot.save.json").read_text()
    play_all(session, [("e2", "e4")])

    def broken_replace(*args):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("session.os.replace", broken_replace)
    with pytest.raises(ValueError, match="Could not save"):
        session.dispatch({"action": "save", "name": "slot", "overwrite": True})
    assert (tmp_path / "slot.save.json").read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == ["slot.save.json"]


def test_save_creates_a_missing_folder(tmp_path):
    session = fresh(tmp_path / "saves" / "nested")
    session.dispatch({"action": "save", "name": "game"})
    assert (tmp_path / "saves" / "nested" / "game.save.json").exists()


def test_saved_games_are_listed_newest_first(tmp_path):
    session = fresh(tmp_path)
    assert session.dispatch({"action": "saves"}) == {"saves": []}
    session.dispatch({"action": "save", "name": "first"})
    play_all(session, [("e2", "e4")])
    session.dispatch({"action": "new", "opponent": "computer"})
    session.dispatch({"action": "save", "name": "second"})
    first = tmp_path / "first.save.json"
    os.utime(first, (first.stat().st_mtime - 60,) * 2)
    (tmp_path / "junk.save.json").write_text("not json")
    (tmp_path / "notes.txt").write_text("ignored")

    saves = session.dispatch({"action": "saves"})["saves"]
    assert [s["name"] for s in saves] == ["second", "first"]
    assert saves[0]["opponent"] == "computer"
    assert saves[1]["moves"] == 0
    assert all(isinstance(s["saved_at"], str) for s in saves)


def test_listing_a_missing_folder_is_empty(tmp_path):
    assert fresh(tmp_path / "absent").dispatch({"action": "saves"}) == {"saves": []}


def test_oversized_files_are_refused(tmp_path):
    (tmp_path / "huge.save.json").write_text(" " * 2_000_000 + "{}")
    with pytest.raises(ValueError, match="too large"):
        fresh(tmp_path).dispatch({"action": "load", "name": "huge"})


def test_deeply_nested_files_are_refused(tmp_path):
    (tmp_path / "deep.save.json").write_text("[" * 200_000 + "]" * 200_000)
    with pytest.raises(ValueError):
        fresh(tmp_path).dispatch({"action": "load", "name": "deep"})


@pytest.mark.parametrize("contents", ["[]", "null", '"text"', "{}"])
def test_files_that_are_not_save_objects_are_refused(tmp_path, contents):
    (tmp_path / "odd.save.json").write_text(contents)
    with pytest.raises(ValueError):
        fresh(tmp_path).dispatch({"action": "load", "name": "odd"})
