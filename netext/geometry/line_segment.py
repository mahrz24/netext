from dataclasses import dataclass
from typing import Sequence
from netext.geometry.point import Point
from shapely.geometry import LineString


@dataclass
class LineSegment:
    start: Point
    end: Point

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
        direct_line = LineString([self.start.shapely_point(), self.end.shapely_point()])
        fraction = distance / float(self.length)
        if reversed:
            fraction = 1 - fraction
        return Point.from_shapely_point(
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
