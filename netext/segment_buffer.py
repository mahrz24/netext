from dataclasses import dataclass
from typing import Any, Tuple

from rich.segment import Segment


@dataclass
class Spacer:
    width: int

    @property
    def cell_length(self) -> int:
        return self.width

    def split_cells(self, at: int) -> Tuple["Spacer", "Spacer"]:
        at = min(max(0, at), self.width)
        return Spacer(at), Spacer(self.width - at)


@dataclass
class Strip:
    segments: list[Segment | Spacer]


@dataclass
class StripBuffer:
    strips: list[Strip]
    z_index: float

    @property
    def left_x(self) -> int:
        return NotImplemented  # pragma: no cover

    @property
    def right_x(self) -> int:
        return NotImplemented  # pragma: no cover

    @property
    def top_y(self) -> int:
        return NotImplemented  # pragma: no cover

    @property
    def bottom_y(self) -> int:
        return NotImplemented  # pragma: no cover

    @property
    def width(self) -> int:
        return NotImplemented  # pragma: no cover

    @property
    def height(self) -> int:
        return NotImplemented  # pragma: no cover

    def __lt__(self, value: Any) -> bool:
        if isinstance(value, StripBuffer):
            return self.left_x < value.left_x
        return False
