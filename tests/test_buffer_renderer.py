import pytest
from pydantic import NonNegativeInt
from rich.console import Console
from rich.segment import Segment, Segments

from netext.buffer_renderer import render_buffers
from netext.segment_buffer import OffsetSegment, SegmentBuffer


class LineBuffer(SegmentBuffer):
    x: NonNegativeInt
    width: NonNegativeInt

    @property
    def left_x(self):
        return self.x

    @property
    def right_x(self):
        return self.x + self.width

    @property
    def top_y(self):
        return 0

    @property
    def bottom_y(self):
        return 0


@pytest.fixture
def console():
    return Console()


def test_simple_render(console):
    test_buffer = LineBuffer(
        x=0,
        width=10,
        segments=[OffsetSegment(segment=Segment(10 * "X"), x_offset=0, y_offset=-0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXXXXXXX\n"
