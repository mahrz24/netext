from dataclasses import dataclass
from netext.geometry.point import Point


@dataclass(frozen=True, slots=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    @staticmethod
    def from_points(u: Point, v: Point) -> "Region":
        return Region(
            x=u.x,
            y=u.y,
            width=v.x - u.x + 1,
            height=v.y - u.y + 1,
        )

    @property
    def top_left(self) -> Point:
        return Point(x=self.x, y=self.y)

    @property
    def bottom_right(self) -> Point:
        return Point(x=self.x + self.width - 1, y=self.y + self.height - 1)

    @property
    def bounding_box(self) -> tuple[int, int, int, int]:
        return self.x, self.y, self.x + self.width - 1, self.y + self.height - 1

    @staticmethod
    def union(regions: list["Region"]) -> "Region":
        return Region.from_points(
            u=Point.min_point([region.top_left for region in regions]),
            v=Point.max_point([region.bottom_right for region in regions]),
        )
