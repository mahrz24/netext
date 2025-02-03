from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FloatPoint:
    x: float
    y: float

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FloatPoint):
            return False
        return self.x == other.x and self.y == other.y

    def __add__(self, other: "FloatPoint") -> "FloatPoint":
        return FloatPoint(x=self.x + other.x, y=self.y + other.y)

    def __sub__(self, other: "FloatPoint") -> "FloatPoint":
        return FloatPoint(x=self.x - other.x, y=self.y - other.y)

    def __mul__(self, scalar: float) -> "FloatPoint":
        return FloatPoint(x=(self.x * scalar), y=(self.y * scalar))

    def __div__(self, scalar: float) -> "FloatPoint":
        return FloatPoint(x=(self.x / scalar), y=(self.y / scalar))

    def __truediv__(self, scalar: float) -> "FloatPoint":
        return FloatPoint(x=(self.x / scalar), y=(self.y / scalar))

    def distance_to(self, other: "FloatPoint") -> float:
        return max(abs(self.x - other.x), abs(self.y - other.y))

    def min_distance_to(self, other: "FloatPoint") -> float:
        return min(abs(self.x - other.x), abs(self.y - other.y))

    def as_tuple(self) -> tuple[float, float]:
        return self.x, self.y

    @staticmethod
    def min_point(points: list["FloatPoint"]) -> "FloatPoint":
        return FloatPoint(
            x=min(point.x for point in points),
            y=min(point.y for point in points),
        )

    @staticmethod
    def max_point(points: list["FloatPoint"]) -> "FloatPoint":
        return FloatPoint(
            x=max(point.x for point in points),
            y=max(point.y for point in points),
        )
