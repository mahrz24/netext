from dataclasses import dataclass

import pytest
from rich.console import Console
from rich.segment import Segment, Segments

from netext.buffer_renderer import render_buffers
from netext.node_rasterizer import NodeBuffer
from netext.segment_buffer import OffsetLine, SegmentBuffer


@dataclass
class LineBuffer(SegmentBuffer):
    x: int
    line_width: int

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

    @property
    def height(self):
        return 1

    @property
    def width(self):
        return self.line_width


@pytest.fixture
def console():
    return Console()


def test_render_trivial(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        segment_lines=[
            OffsetLine(segments=[Segment(10 * "X")], x_offset=0, y_offset=0)
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXXXXXXX\n"


def test_render_trivial_multiple_segments(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        segment_lines=[
            OffsetLine(segments=10 * [Segment("X")], x_offset=0, y_offset=0)
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXXXXXXX\n"


def test_render_segment_with_offset(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        segment_lines=[OffsetLine(segments=[Segment(9 * "X")], x_offset=1, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_buffer_with_offset(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=1,
        line_width=9,
        segment_lines=[OffsetLine(segments=[Segment(9 * "X")], x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_segment_with_offset_cropped(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=11,
        segment_lines=[
            OffsetLine(segments=[Segment(9 * "X" + "Y")], x_offset=1, y_offset=0)
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_segment_with_offset_cropped_multiple_segments(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=11,
        segment_lines=[
            OffsetLine(
                segments=[Segment(9 * "X"), Segment("Y")], x_offset=1, y_offset=0
            )
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_buffer_with_offset_cropped(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=1,
        line_width=10,
        segment_lines=[
            OffsetLine(segments=[Segment(9 * "X" + "Y")], x_offset=0, y_offset=0)
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_fill_remaining_buffer(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        segment_lines=[OffsetLine(segments=[Segment("X")], x_offset=3, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "   X      \n"


def test_render_buffer_with_offset_and_fill_right(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=3,
        line_width=1,
        segment_lines=[OffsetLine(segments=[Segment("X")], x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "   X      \n"


def test_render_segment_empty(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        segment_lines=[OffsetLine(segments=[Segment("")], x_offset=0, y_offset=0)],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "          \n"


def test_render_segment_empty_with_multiple_segments(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        segment_lines=[
            OffsetLine(
                segments=[Segment(""), Segment("X"), Segment(""), Segment("Y")],
                x_offset=0,
                y_offset=0,
            )
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XY        \n"


def test_render_mutliple_buffers(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=2,
            segment_lines=[
                OffsetLine(segments=[Segment("XX")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            z_index=0,
            x=5,
            line_width=2,
            segment_lines=[
                OffsetLine(segments=[Segment("YY")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XX  YY   \n"


def test_render_multiple_buffers_with_overlap(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("XXXXXXXX")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("YY")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXYYXX \n"


def test_render_multiple_buffers_with_overlap_and_multiple_segments(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("XXXXX"), Segment("ZZZ")], x_offset=0, y_offset=0
                ),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("YY")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXYYZZ \n"


def test_render_multiple_buffers_with_overlap_and_multiple_segments_in_overlap(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("XXXXX"), Segment("ZZZ")], x_offset=0, y_offset=0
                ),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=-1,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("Y"), Segment("Y")], x_offset=0, y_offset=0
                ),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXYYZZ \n"


def test_render_multiple_buffers_with_overlap_hidden(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("XXXXXXXX")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=1,
            segment_lines=[
                OffsetLine(segments=[Segment("YY")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXXXXX \n"


def test_render_multiple_buffers_with_overlap_hidden_multiple_segments(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("XXX"), Segment("XXXXX")], x_offset=0, y_offset=0
                ),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=1,
            segment_lines=[
                OffsetLine(segments=[Segment("YY")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXXXXX \n"


def test_render_multiple_buffers_with_nested_overlap(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("ABCDEFGH")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("XYZW")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-2,
            segment_lines=[
                OffsetLine(segments=[Segment("12")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX12WFGH \n"


def test_render_multiple_buffers_with_nested_overlap_multiple_segments(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("ABCD"), Segment("EFGH")], x_offset=0, y_offset=0
                ),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-1,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("XYZ"), Segment("W")], x_offset=0, y_offset=0
                ),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-2,
            segment_lines=[
                OffsetLine(
                    segments=[Segment("1"), Segment("2")], x_offset=0, y_offset=0
                ),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX12WFGH \n"


def test_render_multiple_buffers_with_nested_overlap_one_hidden(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("ABCDEFGH")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-2,
            segment_lines=[
                OffsetLine(segments=[Segment("XYZW")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("12")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AXYZWFGH \n"


def test_render_multiple_buffers_with_multiple_overlaps(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=0,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("ABCDE")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=1,
            line_width=4,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("XYZW")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=4,
            line_width=4,
            z_index=-2,
            segment_lines=[
                OffsetLine(segments=[Segment("1234")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == "AXYZ1234  \n"


def test_render_multiple_buffers_with_multiple_overlaps_middle_in_front(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=0,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("ABCDE")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=1,
            line_width=4,
            z_index=-2,
            segment_lines=[
                OffsetLine(segments=[Segment("XYZW")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=4,
            line_width=4,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("1234")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == "AXYZW234  \n"


def test_render_multiple_buffers_with_empty_segment(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            segment_lines=[
                OffsetLine(segments=[Segment("ABCDEFGH")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=1,
            line_width=4,
            z_index=-1,
            segment_lines=[
                OffsetLine(segments=[Segment("")], x_offset=0, y_offset=0),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=2,
            z_index=-2,
            segment_lines=[
                OffsetLine(segments=[Segment("")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " ABCDEFGH \n"


def test_render_node_buffer(console):
    test_buffer = NodeBuffer(
        z_index=0,
        x=1,
        y=1,
        node_width=3,
        node_height=3,
        segment_lines=[
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=0),
            OffsetLine(segments=[Segment("X X")], x_offset=0, y_offset=1),
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=2),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == " X \nX X\n X \n"


def test_render_node_buffer_with_empty_line(console):
    test_buffer = NodeBuffer(
        z_index=0,
        x=1,
        y=1,
        node_width=3,
        node_height=3,
        segment_lines=[
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=0),
            OffsetLine(segments=[Segment("")], x_offset=0, y_offset=1),
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=2),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == " X \n   \n X \n"


def test_render_node_buffer_with_empty_line_and_no_buffer(console):
    test_buffer = NodeBuffer(
        z_index=0,
        x=1,
        y=1,
        node_width=3,
        node_height=3,
        segment_lines=[
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=0),
            OffsetLine(segments=[Segment("")], x_offset=0, y_offset=1),
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=2),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 4)))

    assert capture.get() == " X \n   \n X \n   \n"


def test_render_node_buffer_with_duplicate_y_offset_fails(console):
    test_buffer = NodeBuffer(
        z_index=0,
        x=1,
        y=1,
        node_width=3,
        node_height=2,
        segment_lines=[
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=0),
            OffsetLine(segments=[Segment("")], x_offset=0, y_offset=0),
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=1),
        ],
    )

    with pytest.raises(
        AssertionError,
        match="Duplicate segments with same y offsets in buffers are not allowed",
    ):
        list(render_buffers([test_buffer], 3, 4))


def test_render_node_buffer_with_missing_y_offset_fails(console):
    test_buffer = NodeBuffer(
        z_index=0,
        x=1,
        y=1,
        node_width=3,
        node_height=3,
        segment_lines=[
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=0),
            OffsetLine(segments=[Segment("X")], x_offset=1, y_offset=2),
        ],
    )

    with pytest.raises(
        AssertionError, match="Buffer does not contain a segment for all rows"
    ):
        list(render_buffers([test_buffer], 3, 4))


def test_render_buffer_with_overflow_segment_fails(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=1,
            segment_lines=[
                OffsetLine(segments=[Segment("AB")], x_offset=0, y_offset=0),
            ],
        ),
    ]

    with pytest.raises(AssertionError, match="Segment overflow"):
        list(render_buffers(test_buffers, 3, 1))


# TODO Overlap with multi segment lines
