from dataclasses import dataclass
from enum import Enum
from typing import Any, Hashable, Tuple

from rich.segment import Segment
from netext.geometry import Region
from netext.geometry.point import Point


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
class Reference:
    type: str
    ref: Hashable


class Layer(Enum):
    BACKGROUND = 0
    EDGES = -1
    EDGE_DECORATIONS = -2
    EDGE_LABELS = -3
    NODES = -4
    PORTS = -5
    PORT_LABELS = -6
    NODE_LABELS = -7
    FOREGROUND = -8

    def __lt__(self, other):
        if isinstance(other, Layer):
            return self.value < other.value
        return NotImplemented

    def __le__(self, other):
        if isinstance(other, Layer):
            return self.value <= other.value
        return NotImplemented

    def __eq__(self, other):
        if isinstance(other, Layer):
            return self.value == other.value
        return NotImplemented

    def __ne__(self, other):
        if isinstance(other, Layer):
            return self.value != other.value
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, Layer):
            return self.value > other.value
        return NotImplemented

    def __ge__(self, other):
        if isinstance(other, Layer):
            return self.value >= other.value
        return NotImplemented


@dataclass
class ZIndex:
    layer: Layer
    layer_index: float = 0

    def __lt__(self, value: Any) -> bool:
        if isinstance(value, ZIndex):
            if self.layer < value.layer:
                return True
            if self.layer == value.layer:
                return self.layer_index < value.layer_index
        return False

    def __le__(self, value: Any) -> bool:
        if isinstance(value, ZIndex):
            if self.layer < value.layer:
                return True
            if self.layer == value.layer:
                return self.layer_index <= value.layer_index
        return False

    def __gt__(self, value: Any) -> bool:
        if isinstance(value, ZIndex):
            if self.layer > value.layer:
                return True
            if self.layer == value.layer:
                return self.layer_index > value.layer_index
        return False

    def __ge__(self, value: Any) -> bool:
        if isinstance(value, ZIndex):
            if self.layer > value.layer:
                return True
            if self.layer == value.layer:
                return self.layer_index >= value.layer_index
        return False

    def __hash__(self) -> int:
        return hash(
            (
                self.layer.value,
                self.layer_index,
            )
        )


@dataclass(kw_only=True)
class StripBuffer:
    strips: list[Strip]
    z_index: ZIndex

    @property
    def reference(self) -> Reference | None:
        return None

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

    @property
    def bounding_box(self) -> tuple[int, int, int, int]:
        return self.left_x, self.top_y, self.right_x, self.bottom_y

    @property
    def region(self) -> Region:
        return Region.from_points(
            Point(self.left_x, self.top_y),
            Point(self.right_x, self.bottom_y),
        )
