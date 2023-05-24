from dataclasses import dataclass, field
from typing import Sequence
from netext.geometry.point import Point
import shapely as sp


@dataclass(frozen=True, slots=True)
class LineSegment:
    start: Point
    end: Point
    _shapely: sp.LineString = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_shapely", None)

    @property
    def shapely(self) -> sp.LineString:
        if self._shapely is None:
            object.__setattr__(
                self, "_shapely", sp.LineString([self.start.shapely, self.end.shapely])
            )
        return self._shapely

    @property
    def length(self) -> int:
        return self.start.distance_to(self.end)

    def horizontal_range(self) -> Sequence[int]:
        if self.start.x <= self.end.x:
            return range(self.start.x, self.end.x + 1)
        else:
            return range(self.start.x, self.end.x - 1, -1)

    def vertical_range(self) -> Sequence[int]:
        if self.start.y <= self.end.y:
            return range(self.start.y, self.end.y + 1)
        else:
            return range(self.start.y, self.end.y - 1, -1)

    def interpolate(self, distance: int, reversed: bool = False) -> Point:
        if self.start == self.end:
            return self.start
        direct_line = self.shapely
        fraction = distance / float(self.length)
        if reversed:
            fraction = 1 - fraction
        return Point.from_shapely(
            direct_line.interpolate(distance=fraction, normalized=True)
        )

    @property
    def midpoint(self) -> Point:
        return (self.start + self.end) / 2

    @property
    def start_y_mid(self) -> Point:
        return Point(x=self.midpoint.x, y=self.start.y)

    @property
    def end_y_mid(self) -> Point:
        return Point(x=self.midpoint.x, y=self.end.y)

    @property
    def start_x_mid(self) -> Point:
        return Point(x=self.start.x, y=self.midpoint.y)

    @property
    def end_x_mid(self) -> Point:
        return Point(x=self.end.x, y=self.midpoint.y)

    @property
    def min_bound(self) -> Point:
        return Point(x=min(self.start.x, self.end.x), y=min(self.start.y, self.end.y))

    @property
    def max_bound(self) -> Point:
        return Point(x=max(self.start.x, self.end.x), y=max(self.start.y, self.end.y))

    @property
    def vertical(self) -> bool:
        return self.start.x == self.end.x

    @property
    def horizontal(self) -> bool:
        return self.start.y == self.end.y

    @property
    def is_point(self) -> bool:
        return self.start == self.end

    @property
    def bounding_box(self) -> tuple[int, int, int, int]:
        return (self.min_bound.x, self.min_bound.y, self.max_bound.x, self.max_bound.y)
