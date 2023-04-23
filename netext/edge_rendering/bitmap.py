from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.rendering.bitmap_buffer import BitmapBuffer
from netext.rendering.segment_buffer import Spacer, Strip


from bitarray import bitarray
from rich.segment import Segment


def _slice_to_strip(slice: bitarray) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for val in slice:
        if not val:
            current_segment.append(Spacer(width=1))
        else:
            current_segment.append(Segment("*"))

    return Strip(segments=current_segment)


def _infinite_canvas_access(slice: bitarray, x: int, y: int, width: int) -> int:
    if width <= 0:
        raise ValueError("Width must be positive")
    index = width * y + x
    if index < 0:
        return 0
    elif index >= len(slice):
        return 0
    else:
        return slice[index]


def _slice_to_braille_strip(slice: bitarray, width: int) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for x in range(0, width, 2):
        lookup = (
            _infinite_canvas_access(slice, x, 0, width),
            _infinite_canvas_access(slice, x, 1, width),
            _infinite_canvas_access(slice, x, 2, width),
            _infinite_canvas_access(slice, x + 1, 0, width),
            _infinite_canvas_access(slice, x + 1, 1, width),
            _infinite_canvas_access(slice, x + 1, 2, width),
            _infinite_canvas_access(slice, x, 3, width),
            _infinite_canvas_access(slice, x + 1, 3, width),
        )
        if all([val == 0 for val in lookup]):
            current_segment.append(Spacer(width=1))
            continue
        current_segment.append(
            Segment(chr(0x2800 + sum([2**i for i, val in enumerate(lookup) if val])))
        )

    return Strip(segments=current_segment)


def _slice_to_block_strip(slice: bitarray, width: int) -> Strip:
    current_segment: list[Segment | Spacer] = []
    for x in range(0, width, 2):
        lookup = (
            _infinite_canvas_access(slice, x, 0, width),
            _infinite_canvas_access(slice, x + 1, 0, width),
            _infinite_canvas_access(slice, x, 1, width),
            _infinite_canvas_access(slice, x + 1, 1, width),
        )
        if all([val == 0 for val in lookup]):
            current_segment.append(Spacer(width=1))
            continue

        block = sum([2**i for i, val in enumerate(lookup) if val])
        match block:
            case 1:
                current_segment.append(Segment("▘"))
            case 2:
                current_segment.append(Segment("▝"))
            case 3:
                current_segment.append(Segment("▀"))
            case 4:
                current_segment.append(Segment("▖"))
            case 5:
                current_segment.append(Segment("▌"))
            case 6:
                current_segment.append(Segment("▞"))
            case 7:
                current_segment.append(Segment("▛"))
            case 8:
                current_segment.append(Segment("▗"))
            case 9:
                current_segment.append(Segment("▚"))
            case 10:
                current_segment.append(Segment("▐"))
            case 11:
                current_segment.append(Segment("▜"))
            case 12:
                current_segment.append(Segment("▄"))
            case 13:
                current_segment.append(Segment("▙"))
            case 14:
                current_segment.append(Segment("▟"))
            case 15:
                current_segment.append(Segment("█"))

    return Strip(segments=current_segment)


def bitmap_to_strips(
    bitmap_buffer: BitmapBuffer, edge_segment_drawing_mode: EdgeSegmentDrawingMode
) -> list[Strip]:
    match edge_segment_drawing_mode:
        case EdgeSegmentDrawingMode.single_character:
            lines = [
                _slice_to_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 1) * bitmap_buffer.width
                    ]
                )
                for y in range(bitmap_buffer.height)
            ]
        case EdgeSegmentDrawingMode.braille:
            lines = [
                _slice_to_braille_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 4) * bitmap_buffer.width
                    ],
                    bitmap_buffer.width,
                )
                for y in range(0, bitmap_buffer.height, 4)
            ]
        case EdgeSegmentDrawingMode.block:
            lines = [
                _slice_to_block_strip(
                    bitmap_buffer.buffer[
                        y * bitmap_buffer.width : (y + 2) * bitmap_buffer.width
                    ],
                    bitmap_buffer.width,
                )
                for y in range(0, bitmap_buffer.height, 2)
            ]
        case _:
            raise NotImplementedError(
                "The edge segement drawing mode has not yet been implemented"
            )

    return lines
