from typing import Any, List, Optional

from pydantic import BaseModel, NonNegativeInt


class OffsetSegment(BaseModel):
    segment: Any  # TODO Should be segment, check pydantic arbitrary types or not use pydantic.

    x_offset: NonNegativeInt  # Offset from left x
    y_offset: NonNegativeInt  # Offset from top y

    def __lt__(self, value):
        if isinstance(value, OffsetSegment):
            return self.x_offset < value.x_offset and self.y_offset == self.y_offset
        return False


class SegmentBuffer(BaseModel):
    segments: List[OffsetSegment]
    z_index: float = 0

    @property
    def left_x(self):
        return NotImplemented

    @property
    def right_x(self):
        return NotImplemented

    @property
    def top_y(self):
        return NotImplemented

    @property
    def bottom_y(self):
        return NotImplemented

    def __lt__(self, value):
        if isinstance(value, SegmentBuffer):
            return self.left_x < value.left_x
        return False