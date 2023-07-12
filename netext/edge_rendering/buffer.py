from typing import Any, Hashable
from netext.geometry import Point
from netext.rendering.segment_buffer import StripBuffer


from dataclasses import dataclass


@dataclass
class EdgeBuffer(StripBuffer):
    edge: tuple[Hashable, Hashable]
    boundary_1: Point
    boundary_2: Point

    @property
    def reference(self) -> Any:
        return self.edge

    @property
    def left_x(self) -> int:
        return min(self.boundary_1.x, self.boundary_2.x)

    @property
    def right_x(self) -> int:
        return max(self.boundary_1.x, self.boundary_2.x)

    @property
    def top_y(self) -> int:
        return min(self.boundary_1.y, self.boundary_2.y)

    @property
    def bottom_y(self) -> int:
        return max(self.boundary_1.y, self.boundary_2.y)

    @property
    def width(self) -> int:
        return self.right_x - self.left_x + 1

    @property
    def height(self) -> int:
        return self.bottom_y - self.top_y + 1
