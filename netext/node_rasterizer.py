from typing import List

from pydantic import BaseModel, NonNegativeInt, PositiveInt
from rich.segment import Segment
from rich.style import Style
from typing import Any

import math

class NodeBuffer(BaseModel):
    x: NonNegativeInt
    y: NonNegativeInt
    width: PositiveInt
    height: PositiveInt
    segments: List[Any] # TODO Should be segment, check pydantic arbitrary types or not use pydantic.


    @property
    def left_x(self):
        return self.x - math.floor(self.width/2)

    @property
    def top_y(self):
        return self.y - math.floor(self.height/2)

    @property
    def bottom_y(self):
        return self.y + math.floor(self.height/2)

    def __lt__(self, value):
        if isinstance(value, NodeBuffer):
            return self.x < value.x
        return False


def rasterize_node(node, data) -> NodeBuffer:
    segment = Segment(str(node), Style(color="red"))
    return NodeBuffer(x=0, y=0, width=segment.cell_length, height=1, segments=[segment])
