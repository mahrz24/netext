from dataclasses import dataclass
from typing import cast

import pytest
from rich.console import Console
from rich.segment import Segment, Segments

from netext.buffer_renderer import render_buffers
from netext.geometry import Point
from netext.node_rasterizer import NodeBuffer
from netext.rendering.segment_buffer import Strip, StripBuffer, Spacer


@dataclass
class LineBuffer(StripBuffer):
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
        strips=[Strip(segments=[Segment(10 * "X")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXXXXXXX\n"


def test_render_spacer_trivial(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[Strip(segments=[Spacer(width=10)])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "          \n"


def test_render_trivial_multiple_segments(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[Strip(segments=cast(list[Segment | Spacer], 10 * [Segment("X")]))],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXXXXXXX\n"


def test_render_trivial_multiple_segments_spacers(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[
            Strip(
                segments=5 * [cast(Segment | Spacer, Segment("X"))]
                + 5 * [cast(Segment | Spacer, Spacer(width=1))]
            )
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "XXXXX     \n"


def test_render_multiple_segments_spacers_layered(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=0,
            line_width=9,
            strips=[
                Strip(
                    segments=3 * [cast(Segment | Spacer, Spacer(width=1))]
                    + 3 * [cast(Segment | Spacer, Segment("X"))]
                    + 3 * [cast(Segment | Spacer, Spacer(width=1))],
                )
            ],
        ),
        LineBuffer(
            z_index=0,
            x=2,
            line_width=6,
            strips=[
                Strip(
                    segments=3 * [cast(Segment | Spacer, Spacer(width=1))]
                    + 3 * [cast(Segment | Spacer, Segment("Y"))],
                )
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == "   XXXYY  \n"


def test_render_segment_with_offset(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[Strip(segments=[Spacer(width=1), Segment(9 * "X")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_buffer_with_offset(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=1,
        line_width=9,
        strips=[Strip(segments=[Segment(9 * "X")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_segment_with_offset_cropped(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=11,
        strips=[Strip(segments=[Spacer(width=1), Segment(9 * "X" + "Y")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_segment_with_offset_cropped_multiple_segments(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=11,
        strips=[Strip(segments=[Spacer(width=1), Segment(9 * "X"), Segment("Y")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_buffer_with_offset_cropped(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=1,
        line_width=10,
        strips=[Strip(segments=[Segment(9 * "X" + "Y")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == " XXXXXXXXX\n"


def test_render_fill_remaining_buffer(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[Strip(segments=[Spacer(width=3), Segment("X")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "   X      \n"


def test_render_buffer_with_offset_and_fill_right(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=3,
        line_width=1,
        strips=[Strip(segments=[Segment("X")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "   X      \n"


def test_render_segment_empty(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[Strip(segments=[Segment("")])],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 10, 1)))

    assert capture.get() == "          \n"


def test_render_segment_empty_with_multiple_segments(console):
    test_buffer = LineBuffer(
        z_index=0,
        x=0,
        line_width=10,
        strips=[Strip(segments=[Segment(""), Segment("X"), Segment(""), Segment("Y")])],
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
            strips=[
                Strip(segments=[Segment("XX")]),
            ],
        ),
        LineBuffer(
            z_index=0,
            x=5,
            line_width=2,
            strips=[
                Strip(segments=[Segment("YY")]),
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
            strips=[
                Strip(segments=[Segment("XXXXXXXX")]),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("YY")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXYYXX \n"


def test_render_multiple_buffers_with_overlap_and_spacer(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            strips=[
                Strip(segments=[Segment("XXXXXXXX")]),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(
                    segments=[Segment("Y"), Spacer(width=2), Segment("Y")],
                ),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " XXXXYXXY \n"


def test_render_multiple_buffers_with_overlap_and_multiple_segments(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            strips=[
                Strip(segments=[Segment("XXXXX"), Segment("ZZZ")]),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("YY")]),
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
            strips=[
                Strip(segments=[Segment("XXXXX"), Segment("ZZZ")]),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("Y"), Segment("Y")]),
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
            strips=[
                Strip(segments=[Segment("XXXXXXXX")]),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=1,
            strips=[
                Strip(segments=[Segment("YY")]),
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
            strips=[
                Strip(segments=[Segment("XXX"), Segment("XXXXX")]),
            ],
        ),
        LineBuffer(
            x=5,
            line_width=2,
            z_index=1,
            strips=[
                Strip(segments=[Segment("YY")]),
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
            strips=[
                Strip(segments=[Segment("ABCDEFGH")]),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("XYZW")]),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("12")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX12WFGH \n"


def test_render_multiple_buffers_with_nested_overlap_multiple_segments(console):
    test_buffers = [
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("XYZ"), Segment("W")]),
            ],
        ),
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            strips=[
                Strip(segments=[Segment("ABCD"), Segment("EFGH")]),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("1"), Segment("2")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX12WFGH \n"


def test_render_multiple_buffers_with_nested_overlap_multiple_segments_different_z_order(
    console,
):
    test_buffers = [
        LineBuffer(
            x=2,
            line_width=4,
            z_index=0,
            strips=[
                Strip(segments=[Segment("XYZ"), Segment("W")]),
            ],
        ),
        LineBuffer(
            z_index=-1,
            x=1,
            line_width=8,
            strips=[
                Strip(segments=[Segment("ABCD"), Segment("EFGH")]),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("1"), Segment("2")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AB12EFGH \n"


def test_render_multiple_buffers_with_nested_overlap_multiple_segments_and_spacers(
    console,
):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            strips=[
                Strip(segments=[Segment("ABCD"), Segment("EFGH")]),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("XYZ"), Segment("W")]),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=3,
            z_index=-2,
            strips=[
                Strip(
                    segments=[Segment("1"), Spacer(width=1), Segment("2")],
                ),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX1Z2FGH \n"


def test_render_multiple_buffers_with_nested_overlap_one_hidden(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            strips=[
                Strip(segments=[Segment("ABCDEFGH")]),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("XYZW")]),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("12")]),
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
            strips=[
                Strip(segments=[Segment("ABCDE")]),
            ],
        ),
        LineBuffer(
            x=1,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("XYZW")]),
            ],
        ),
        LineBuffer(
            x=4,
            line_width=4,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("1234")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == "AXYZ1234  \n"


def test_render_multiple_buffers_with_nested_overlap_one_hidden_multiple_spacers(
    console,
):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=8,
            strips=[
                Strip(
                    segments=[Segment("A"), Spacer(width=1), Segment("CDEFGH")],
                ),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=4,
            z_index=-2,
            strips=[
                Strip(
                    segments=[Segment("X"), Spacer(width=2), Segment("W")],
                ),
            ],
        ),
        LineBuffer(
            x=3,
            line_width=2,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("12")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " AX12WFGH \n"


def test_render_multiple_buffers_with_multiple_overlaps_middle_in_front(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=0,
            line_width=8,
            strips=[
                Strip(segments=[Segment("ABCDE")]),
            ],
        ),
        LineBuffer(
            x=1,
            line_width=4,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("XYZW")]),
            ],
        ),
        LineBuffer(
            x=4,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("1234")]),
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
            strips=[
                Strip(segments=[Segment("ABCDEFGH")]),
            ],
        ),
        LineBuffer(
            x=1,
            line_width=4,
            z_index=-1,
            strips=[
                Strip(segments=[Segment("")]),
            ],
        ),
        LineBuffer(
            x=2,
            line_width=2,
            z_index=-2,
            strips=[
                Strip(segments=[Segment("")]),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 10, 1)))

    assert capture.get() == " ABCDEFGH \n"


def test_render_node_buffer(console):
    test_buffer = NodeBuffer(
        z_index=0,
        center=Point(x=1, y=1),
        node_width=3,
        node_height=3,
        strips=[
            Strip(segments=[Spacer(width=1), Segment("X")]),
            Strip(segments=[Segment("X X")]),
            Strip(segments=[Spacer(width=1), Segment("X")]),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == " X \nX X\n X \n"


def test_render_node_buffer_with_spacers(console):
    test_buffer = NodeBuffer(
        z_index=0,
        center=Point(x=1, y=1),
        node_width=3,
        node_height=3,
        strips=[
            Strip(segments=[Segment("X"), Spacer(width=1), Spacer(width=1)]),
            Strip(
                segments=[Spacer(width=1), Segment("X"), Spacer(width=1)],
            ),
            Strip(
                segments=[Spacer(width=1), Spacer(width=1), Segment("X")],
            ),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == "X  \n X \n  X\n"


def test_render_node_buffers_with_spacers(console):
    test_buffers = [
        NodeBuffer(
            z_index=0,
            center=Point(x=1, y=1),
            node_width=3,
            node_height=3,
            strips=[
                Strip(
                    segments=[Segment("X"), Spacer(width=1), Spacer(width=1)],
                ),
                Strip(
                    segments=[Spacer(width=1), Segment("X"), Spacer(width=1)],
                ),
                Strip(
                    segments=[Spacer(width=1), Spacer(width=1), Segment("X")],
                ),
            ],
        ),
        NodeBuffer(
            z_index=1,
            center=Point(x=1, y=1),
            node_width=3,
            node_height=3,
            strips=[
                Strip(
                    segments=[Spacer(width=1), Segment("Y"), Spacer(width=1)],
                ),
                Strip(
                    segments=[Spacer(width=1), Segment("Y"), Segment("Y")],
                ),
                Strip(
                    segments=[Spacer(width=1), Segment("Y"), Spacer(width=1)],
                ),
            ],
        ),
    ]

    with console.capture() as capture:
        console.print(Segments(render_buffers(test_buffers, 3, 3)))

    assert capture.get() == "XY \n XY\n YX\n"


def test_render_node_buffer_with_empty_line(console):
    test_buffer = NodeBuffer(
        z_index=0,
        center=Point(x=1, y=1),
        node_width=3,
        node_height=3,
        strips=[
            Strip(segments=[Spacer(width=1), Segment("X")]),
            Strip(segments=[Segment("")]),
            Strip(segments=[Spacer(width=1), Segment("X")]),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 3)))

    assert capture.get() == " X \n   \n X \n"


def test_render_node_buffer_with_empty_line_and_no_buffer(console):
    test_buffer = NodeBuffer(
        z_index=0,
        center=Point(x=1, y=1),
        node_width=3,
        node_height=3,
        strips=[
            Strip(segments=[Spacer(width=1), Segment("X")]),
            Strip(segments=[Segment("")]),
            Strip(segments=[Spacer(width=1), Segment("X")]),
        ],
    )

    with console.capture() as capture:
        console.print(Segments(render_buffers([test_buffer], 3, 4)))

    assert capture.get() == " X \n   \n X \n   \n"


def test_render_buffer_with_overflow_segment_fails(console):
    test_buffers = [
        LineBuffer(
            z_index=0,
            x=1,
            line_width=1,
            strips=[
                Strip(segments=[Segment("AB")]),
            ],
        ),
    ]

    with pytest.raises(AssertionError, match="Segment overflow"):
        list(render_buffers(test_buffers, 3, 1))


# TODO Overlap with multi segment lines
