import pytest
from pydantic import NonNegativeInt
from rich.console import Console
from rich.segment import Segment, Segments

from netext.buffer_renderer import render_buffers
from netext.node_rasterizer import NodeBuffer
from netext.segment_buffer import OffsetSegment, SegmentBuffer


class LineBuffer(SegmentBuffer):
    x: NonNegativeInt
    width: NonNegativeInt

    @property
    def left_x(self):
        return self.x

    @property
    def right_x(self):
        return self.x + self.width - 1

    @property
    def top_y(self):
        return 0

    @property
    def bottom_y(self):
        return 0


@pytest.fixture
def console():
    return Console()


def test_render_trivial(console):
    test_buffer = LineBuffer(
        x=0,
        width=10,
        segments=[OffsetSegment(segment=Segment(10 * "X"), x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXXXXXXX\n"


def test_render_segment_with_offset(console):
    test_buffer = LineBuffer(
        x=0,
        width=10,
        segments=[OffsetSegment(segment=Segment(9 * "X"), x_offset=1, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_buffer_with_offset(console):
    test_buffer = LineBuffer(
        x=1,
        width=9,
        segments=[OffsetSegment(segment=Segment(9 * "X"), x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_segment_with_offset_cropped(console):
    test_buffer = LineBuffer(
        x=0,
        width=11,
        segments=[
            OffsetSegment(segment=Segment(9 * "X" + "Y"), x_offset=1, y_offset=0)
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_buffer_with_offset_cropped(console):
    test_buffer = LineBuffer(
        x=1,
        width=10,
        segments=[
            OffsetSegment(segment=Segment(9 * "X" + "Y"), x_offset=0, y_offset=0)
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_fill_remaining_buffer(console):
    test_buffer = LineBuffer(
        x=0,
        width=10,
        segments=[OffsetSegment(segment=Segment("X"), x_offset=3, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "   X      \n"


def test_render_buffer_with_offset_and_fill_right(console):
    test_buffer = LineBuffer(
        x=3,
        width=1,
        segments=[OffsetSegment(segment=Segment("X"), x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "   X      \n"


def test_render_segment_empty(console):
    test_buffer = LineBuffer(
        x=0,
        width=10,
        segments=[OffsetSegment(segment=Segment(""), x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "          \n"


def test_render_mutliple_buffers(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=2,
            segments=[
                OffsetSegment(segment=Segment("XX"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=5,
            width=2,
            segments=[
                OffsetSegment(segment=Segment("YY"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XX  YY   \n"


def test_render_multiple_buffers_with_overlap(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("XXXXXXXX"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=5,
            width=2,
            z_index=-1,
            segments=[
                OffsetSegment(segment=Segment("YY"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXYYXX \n"


def test_render_multiple_buffers_with_overlap_hidden(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("XXXXXXXX"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=5,
            width=2,
            z_index=1,
            segments=[
                OffsetSegment(segment=Segment("YY"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXXXXX \n"


def test_render_multiple_buffers_with_nested_overlap(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("ABCDEFGH"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=2,
            width=4,
            z_index=-1,
            segments=[
                OffsetSegment(segment=Segment("XYZW"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=3,
            width=2,
            z_index=-2,
            segments=[
                OffsetSegment(segment=Segment("12"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX12WFGH \n"


def test_render_multiple_buffers_with_nested_overlap_one_hidden(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("ABCDEFGH"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=2,
            width=4,
            z_index=-2,
            segments=[
                OffsetSegment(segment=Segment("XYZW"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=3,
            width=2,
            z_index=-1,
            segments=[
                OffsetSegment(segment=Segment("12"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AXYZWFGH \n"


def test_render_multiple_buffers_with_multiple_overlaps(console):
    test_buffers = [
        LineBuffer(
            x=0,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("ABCDE"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=1,
            width=4,
            z_index=-1,
            segments=[
                OffsetSegment(segment=Segment("XYZW"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=4,
            width=4,
            z_index=-2,
            segments=[
                OffsetSegment(segment=Segment("1234"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == "AXYZ1234  \n"


def test_render_multiple_buffers_with_multiple_overlaps_middle_in_front(console):
    test_buffers = [
        LineBuffer(
            x=0,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("ABCDE"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=1,
            width=4,
            z_index=-2,
            segments=[
                OffsetSegment(segment=Segment("XYZW"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=4,
            width=4,
            z_index=-1,
            segments=[
                OffsetSegment(segment=Segment("1234"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == "AXYZW234  \n"


def test_render_multiple_buffers_with_empty_segment(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=8,
            segments=[
                OffsetSegment(segment=Segment("ABCDEFGH"), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=1,
            width=4,
            z_index=-1,
            segments=[
                OffsetSegment(segment=Segment(""), x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=2,
            width=2,
            z_index=-2,
            segments=[
                OffsetSegment(segment=Segment(""), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " ABCDEFGH \n"


def test_render_node_buffer(console):
    test_buffer = NodeBuffer(
        x=1,
        y=1,
        width=3,
        height=3,
        segments=[
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=0),
            OffsetSegment(segment=Segment("X X"), x_offset=0, y_offset=1),
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=2),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == " X \nX X\n X \n"


def test_render_node_buffer_with_empty_line(console):
    test_buffer = NodeBuffer(
        x=1,
        y=1,
        width=3,
        height=3,
        segments=[
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=0),
            OffsetSegment(segment=Segment(""), x_offset=0, y_offset=1),
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=2),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == " X \n   \n X \n"


def test_render_node_buffer_with_empty_line_and_no_buffer(console):
    test_buffer = NodeBuffer(
        x=1,
        y=1,
        width=3,
        height=3,
        segments=[
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=0),
            OffsetSegment(segment=Segment(""), x_offset=0, y_offset=1),
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=2),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 4)))

    assert capture.get() == " X \n   \n X \n   \n"


def test_render_node_buffer_with_duplicate_y_offset_fails(console):
    test_buffer = NodeBuffer(
        x=1,
        y=1,
        width=3,
        height=2,
        segments=[
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=0),
            OffsetSegment(segment=Segment(""), x_offset=0, y_offset=0),
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=1),
        ],
    )

    with pytest.raises(
        AssertionError,
        match="Duplicate segments with same y offsets in buffers are not allowed",
    ):
        list(render_buffers([test_buffer], 3, 4))


def test_render_node_buffer_with_missing_y_offset_fails(console):
    test_buffer = NodeBuffer(
        x=1,
        y=1,
        width=3,
        height=3,
        segments=[
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=0),
            OffsetSegment(segment=Segment("X"), x_offset=1, y_offset=2),
        ],
    )

    with pytest.raises(
        AssertionError, match="Buffer does not contain a segment for all rows"
    ):
        list(render_buffers([test_buffer], 3, 4))


def test_render_buffer_with_overflow_segment_fails(console):
    test_buffers = [
        LineBuffer(
            x=1,
            width=1,
            segments=[
                OffsetSegment(segment=Segment("AB"), x_offset=0, y_offset=0),
            ],
        ),
    ]

    with pytest.raises(AssertionError, match="Segment overflow"):
        list(render_buffers(test_buffers, 3, 1))
