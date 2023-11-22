from bitarray import bitarray
from netext.rendering.segment_buffer import Strip
from netext.rendering.segment_buffer import Spacer
from netext.edge_rendering.bitmap import _slice_to_strip
from rich.segment import Segment
from rich.style import Style


# Tests that the function correctly converts a slice of all zeros to a Strip object
def test_all_zeros():
    slice = bitarray("0" * 10)
    expected_strip = Strip(segments=[Spacer(width=1)] * 10)
    assert _slice_to_strip(slice) == expected_strip


# Tests that the function correctly converts a slice of all ones to a Strip object
def test_all_ones():
    slice = bitarray("1" * 10)
    expected_strip = Strip(segments=[Segment("*")] * 10)
    assert _slice_to_strip(slice) == expected_strip


# Tests that the function correctly converts a slice of alternating zeros
# and ones to a Strip object
def test_alternating_zeros_and_ones():
    slice = bitarray("0101010101")
    expected_strip = Strip(
        segments=[
            Spacer(width=1),
            Segment("*"),
            Spacer(width=1),
            Segment("*"),
            Spacer(width=1),
            Segment("*"),
            Spacer(width=1),
            Segment("*"),
            Spacer(width=1),
            Segment("*"),
        ]
    )
    assert _slice_to_strip(slice) == expected_strip


# Tests that the function correctly converts a slice of length 1 to a Strip object
def test_length_1():
    slice = bitarray("1")
    expected_strip = Strip(segments=[Segment("*")])
    assert _slice_to_strip(slice) == expected_strip


# Tests that the function correctly converts a slice of length 10 to a Strip object
def test_length_10():
    slice = bitarray("1111000000")
    expected_strip = Strip(segments=[Segment("*")] * 4 + [Spacer(width=1)] * 6)
    assert _slice_to_strip(slice) == expected_strip


# Tests that the function correctly handles an empty slice
def test_empty_slice():
    slice = bitarray()
    expected_strip = Strip(segments=[])
    assert _slice_to_strip(slice) == expected_strip


# Tests that _slice_to_strip correctly converts a slice with a style parameter into a Strip with Segments
def test_slice_with_style_parameter():
    slice = bitarray("1111")
    style = Style(color="red")
    expected_strip = Strip(segments=[Segment("*", style=style)] * 4)
    assert _slice_to_strip(slice, style=style) == expected_strip
