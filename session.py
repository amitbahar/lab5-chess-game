"""Application actions and information shown beside the board."""

import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from captured import missing_pieces
from computer import choose_move
from game import (
    legal_moves,
    move,
    new_position,
    promotes,
    status,
    winner,
)

# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"), ("h7", "h5"),
    ("a4", "a5"), ("h5", "h4"),
    ("a5", "a6"), ("h4", "h3"),
    ("a6", "b7"), ("h3", "g2"),
]

SAVE_FORMAT = "chess-workshop-save"
SAVE_VERSION = 1
SAVE_SUFFIX = ".save.json"
SAVE_NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")
# Far above any real game; stops a huge file from being read into memory.
MAX_SAVE_BYTES = 1_000_000


def read_save(path: Path) -> dict[str, Any]:
    """Read a save file's JSON object, checking only its size, syntax and header."""
    try:
        with path.open("rb") as file:
            raw = file.read(MAX_SAVE_BYTES + 1)
    except FileNotFoundError:
        raise ValueError(f"No saved game named {path.name[:-len(SAVE_SUFFIX)]}") from None
    except OSError:
        raise ValueError("Could not read the saved game") from None
    if len(raw) > MAX_SAVE_BYTES:
        raise ValueError("The saved game is too large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("Could not read the saved game") from None
    if (not isinstance(data, dict) or data.get("format") != SAVE_FORMAT
            or data.get("version") != SAVE_VERSION):
        raise ValueError("Not a saved game this version can read")
    return data


class Session:
    # Where saved games are written. Kept outside reset() so a new game keeps it.
    save_dir = Path(__file__).parent

    def __init__(self, opponent="human"):
        self.reset(opponent)

    def reset(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        self.captured = []
        self.opponent = opponent
        # Every move from the starting position, as play() keyword arguments, so
        # earlier positions can be rebuilt. Shared by save/load and undo.
        self.history: list[dict[str, str]] = []

    def play(self, source, target, promotion=None):
        label = move(self.position, source, target, promotion)
        self.notation.append(label)
        step = {"source": source, "target": target}
        if promotion is not None:
            step["promotion"] = promotion
        self.history.append(step)
        self.after_move()

    def save_path(self, name: object) -> Path:
        if not isinstance(name, str) or not SAVE_NAME.fullmatch(name):
            raise ValueError("Save names use letters, digits, - and _ only")
        return Path(self.save_dir) / (name + SAVE_SUFFIX)

    def snapshot(self) -> dict[str, Any]:
        return {
            "format": SAVE_FORMAT,
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "turn": self.position[1],
            "board": self.position[0],
            "moves": self.notation,
            "history": self.history,
        }

    def save(self, name: object, overwrite: bool = False) -> None:
        """Write the game to <name>.save.json. The file is replaced in one step, so a
        failed save never leaves a half-written file behind."""
        path = self.save_path(name)
        if path.exists() and not overwrite:
            raise ValueError(f"A saved game named {name} already exists")
        text = json.dumps(self.snapshot(), indent=2) + "\n"
        temporary = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                    "w", encoding="utf-8", dir=path.parent, prefix=f".{name}.",
                    suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                file.write(text)
            os.replace(temporary, path)
        except OSError as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            reason = error.strerror or "the file could not be written"
            raise ValueError(f"Could not save the game: {reason}") from None

    def load(self, name: object) -> None:
        """Replace this game with a saved one. The file is checked by replaying its
        history, so a damaged or edited file leaves the current game unchanged."""
        data = read_save(self.save_path(name))
        history = data.get("history")
        if not isinstance(history, list) or not all(
                isinstance(step, dict) and {"source", "target"} <= set(step)
                and set(step) <= {"source", "target", "promotion"}
                for step in history):
            raise ValueError("The saved game's history is damaged")
        restored = type(self)(data.get("opponent"))
        try:
            for step in history:
                restored.play(**step)
        except ValueError:
            raise ValueError("The saved game contains an illegal move") from None
        if (restored.position[0] != data.get("board")
                or restored.position[1] != data.get("turn")
                or restored.notation != data.get("moves")):
            raise ValueError("The saved game does not match its move history")
        self.__dict__.update(restored.__dict__)

    def saved_games(self) -> list[dict[str, Any]]:
        """Readable saves in the save folder, newest first. Unreadable files are skipped."""
        folder = Path(self.save_dir)
        if not folder.is_dir():
            return []
        found = []
        for path in folder.glob("*" + SAVE_SUFFIX):
            name = path.name[:-len(SAVE_SUFFIX)]
            if not SAVE_NAME.fullmatch(name):
                continue
            try:
                data = read_save(path)
                modified = path.stat().st_mtime
            except (ValueError, OSError):
                continue
            moves = data.get("moves")
            found.append((modified, {
                "name": name,
                "opponent": data.get("opponent"),
                "moves": len(moves) if isinstance(moves, list) else 0,
                "saved_at": datetime.fromtimestamp(modified).isoformat(timespec="seconds"),
            }))
        found.sort(key=lambda entry: entry[0], reverse=True)
        return [entry for _, entry in found]

    def undo(self) -> None:
        """Take back the last move; against the computer, also its reply.

        Does nothing when no move has been played.
        """
        if not self.history:
            return
        # Against the computer, return to the player's turn (White).
        steps = 2 if self.opponent == "computer" and self.position[1] == "w" else 1
        moves = self.history[:-steps]
        self.reset(self.opponent)
        for step in moves:
            self.play(**step)

    def after_move(self):
        self.captured = missing_pieces(self.position)

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "can_undo": bool(self.history),
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        return {"captured": self.captured}

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"), action.get("promotion"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "legal":
            source = action.get("source")
            targets = legal_moves(self.position, source)
            return {"targets": targets,
                    "promotions": [t for t in targets if promotes(self.position, source, t)]}
        elif command == "undo":
            self.undo()
        elif command == "new":
            self.reset(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.reset()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        elif command == "save":
            self.save(action.get("name"), overwrite=action.get("overwrite") is True)
        elif command == "load":
            self.load(action.get("name"))
        elif command == "saves":
            return {"saves": self.saved_games()}
        else:
            raise ValueError("Unknown action")
        return self.view()
