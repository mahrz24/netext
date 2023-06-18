from dataclasses import dataclass, field
import shapely as sp


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int
    _shapely: sp.Point = field(init=False, repr=False)

    def __post_init__(self):
        object.__setattr__(self, "_shapely", None)

    @property
    def shapely(self) -> sp.Point:
        if self._shapely is None:
            object.__setattr__(self, "_shapely", sp.Point([self.x, self.y]))
        return self._shapely

    @classmethod
    def from_shapely(cls, point: sp.Point) -> "Point":
        return cls(x=round(point.x), y=round(point.y))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return False
        return self.x == other.x and self.y == other.y

    def __add__(self, other: "Point") -> "Point":
        return Point(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(x=self.x - other.x, y=self.y - other.y)

    def __mul__(self, scalar: float | int) -> "Point":
        return Point(x=round(self.x * scalar), y=round(self.y * scalar))

    def __div__(self, scalar: float | int) -> "Point":
        return Point(x=round(self.x / scalar), y=round(self.y / scalar))

    def __truediv__(self, scalar: float | int) -> "Point":
        return Point(x=round(self.x / scalar), y=round(self.y / scalar))

    def distance_to(self, other: "Point") -> int:
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def min_distance_to(self, other: "Point") -> int:
        return min(abs(self.x - other.x), abs(self.y - other.y))

    @staticmethod
    def min_point(points: list["Point"]) -> "Point":
        return Point(
            x=min(point.x for point in points),
            y=min(point.y for point in points),
        )

    @staticmethod
    def max_point(points: list["Point"]) -> "Point":
        return Point(
            x=max(point.x for point in points),
            y=max(point.y for point in points),
        )
