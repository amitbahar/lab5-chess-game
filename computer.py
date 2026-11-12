"""A computer opponent that looks one move ahead."""

import random
from collections.abc import Iterator

from game import (
    PROMOTION_PIECES,
    Position,
    copy_position,
    legal_moves,
    move,
    promotes,
    status,
)

VALUES = {"P": 1, "N": 3, "B": 3, "R": 5, "Q": 9, "K": 0}
CHECKMATE = 1000

# (source, target) or (source, target, promotion piece): arguments for move().
Candidate = tuple[str, str] | tuple[str, str, str]


def candidate_moves(position: Position) -> Iterator[Candidate]:
    board, turn = position[:2]
    for source, piece in sorted(board.items()):
        if piece[0] == turn:
            for target in legal_moves(position, source):
                if promotes(position, source, target):
                    for piece in PROMOTION_PIECES:
                        yield (source, target, piece)
                else:
                    yield (source, target)


def evaluate(position: Position, side: str) -> int:
    """Score a position for side: material, unless the game is over."""
    result = status(position)
    if result == "checkmate":
        return CHECKMATE if position[1] != side else -CHECKMATE
    if result == "stalemate":
        return 0
    return sum(VALUES[piece[1]] * (1 if piece[0] == side else -1)
               for piece in position[0].values())


def choose_move(
    position: Position, rng: random.Random | None = None
) -> Candidate | None:
    """Return the move with the best score after it, or None if there is no move."""
    side = position[1]
    best: list[Candidate] = []
    best_score: int | None = None
    for candidate in candidate_moves(position):
        trial = copy_position(position)
        move(trial, *candidate)
        score = evaluate(trial, side)
        if best_score is None or score > best_score:
            best, best_score = [candidate], score
        elif score == best_score:
            best.append(candidate)
    return (rng or random).choice(best) if best else None
