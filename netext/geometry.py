from dataclasses import dataclass
from enum import Enum
import shapely as sp


@dataclass
class Point:
    x: int
    y: int

    def shapely_point(self) -> sp.Point:
        return sp.Point([self.x, self.y])

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

    def distance_to(self, other: "Point") -> float:
        return self.shapely_point().distance(other.shapely_point())


class Magnet(Enum):
    CENTER = 0
    TOP = 1
    LEFT = 2
    BOTTOM = 3
    RIGHT = 4
    CLOSEST = 5
