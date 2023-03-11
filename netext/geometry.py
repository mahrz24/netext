from dataclasses import dataclass
from enum import Enum
import shapely as sp


@dataclass
class Point:
    x: int
    y: int

    def shapely_point(self) -> sp.Point:
        return sp.Point([self.x, self.y])


class Magnet(Enum):
    CENTER = 0
    TOP = 1
    LEFT = 2
    BOTTOM = 3
    RIGHT = 4
