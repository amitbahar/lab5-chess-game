"""Application actions and information shown beside the board."""

import json
import re
from pathlib import Path

from computer import choose_move
from game import (
    legal_moves,
    move,
    new_position,
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


class Session:
    # Where saved games are written. Kept outside __init__ so a new game keeps it.
    save_dir = Path(__file__).parent

    def __init__(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        self.opponent = opponent
        # Every move from the starting position, so earlier positions can be rebuilt.
        self.history = []

    def play(self, source, target):
        label = move(self.position, source, target)
        self.notation.append(label)
        self.history.append({"source": source, "target": target})
        self.after_move()

    def save_path(self, name):
        if not isinstance(name, str) or not SAVE_NAME.fullmatch(name):
            raise ValueError("Save names use letters, digits, - and _ only")
        return Path(self.save_dir) / (name + SAVE_SUFFIX)

    def snapshot(self):
        return {
            "format": SAVE_FORMAT,
            "version": SAVE_VERSION,
            "opponent": self.opponent,
            "turn": self.position[1],
            "board": self.position[0],
            "moves": self.notation,
            "history": self.history,
        }

    def save(self, name):
        path = self.save_path(name)
        try:
            path.write_text(json.dumps(self.snapshot(), indent=2) + "\n")
        except OSError as error:
            raise ValueError(f"Could not save the game: {error.strerror}") from None

    def load(self, name):
        """Replace this game with a saved one. The file is checked by replaying its
        history, so a damaged or edited file leaves the current game unchanged."""
        path = self.save_path(name)
        try:
            data = json.loads(path.read_text())
        except FileNotFoundError:
            raise ValueError(f"No saved game named {name}") from None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("Could not read the saved game") from None
        if (not isinstance(data, dict) or data.get("format") != SAVE_FORMAT
                or data.get("version") != SAVE_VERSION):
            raise ValueError("Not a saved game this version can read")
        history = data.get("history")
        if not isinstance(history, list) or not all(
                isinstance(step, dict) and set(step) == {"source", "target"}
                for step in history):
            raise ValueError("The saved game's history is damaged")
        restored = type(self)(data.get("opponent"))
        try:
            for step in history:
                restored.play(step["source"], step["target"])
        except ValueError:
            raise ValueError("The saved game contains an illegal move") from None
        if (restored.position[0] != data.get("board")
                or restored.position[1] != data.get("turn")
                or restored.notation != data.get("moves")):
            raise ValueError("The saved game does not match its move history")
        self.__dict__.update(restored.__dict__)

    def after_move(self):
        pass

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        return {}

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "legal":
            return {"targets": legal_moves(self.position, action.get("source"))}
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        elif command == "save":
            self.save(action.get("name"))
        elif command == "load":
            self.load(action.get("name"))
        else:
            raise ValueError("Unknown action")
        return self.view()
