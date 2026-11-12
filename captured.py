"""Counts for the captured-pieces sidebar."""

from collections import Counter

from game import Position, new_position


def missing_pieces(position: Position) -> list[str]:
    initial: Counter[str] = Counter(new_position()[0].values())
    current = Counter(position[0].values())
    return sorted((initial - current).elements())
