from enum import Enum
from netext.edge_routing.edge import EdgeSegment
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.geometry import Point
from netext.rendering.segment_buffer import Spacer, Strip


from rich.segment import Segment
from rich.style import Style


class EdgeCharacters(Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    CORNER_UPPER_LEFT = "corner_upper_left"
    CORNER_UPPER_RIGHT = "corner_upper_right"
    CORNER_LOWER_LEFT = "corner_lower_left"
    CORNER_LOWER_RIGHT = "corner_lower_right"


edge_characters = {
    EdgeSegmentDrawingMode.BOX: {
        EdgeCharacters.HORIZONTAL: "─",
        EdgeCharacters.VERTICAL: "│",
        EdgeCharacters.CORNER_UPPER_LEFT: "╭",
        EdgeCharacters.CORNER_UPPER_RIGHT: "╮",
        EdgeCharacters.CORNER_LOWER_LEFT: "╰",
        EdgeCharacters.CORNER_LOWER_RIGHT: "╯",
    },
    EdgeSegmentDrawingMode.ASCII: {
        EdgeCharacters.HORIZONTAL: "-",
        EdgeCharacters.VERTICAL: "|",
        EdgeCharacters.CORNER_LOWER_LEFT: "+",
        EdgeCharacters.CORNER_LOWER_RIGHT: "+",
        EdgeCharacters.CORNER_UPPER_LEFT: "+",
        EdgeCharacters.CORNER_UPPER_RIGHT: "+",
    },
}


def orthogonal_segments_to_strips_with_box_characters(
    edge_segments: list[EdgeSegment],
    drawing_mode: EdgeSegmentDrawingMode,
    style: Style | None = None,
) -> list[Strip]:
    if not edge_segments:
        return []

    min_point = Point(
        x=min([min([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=min([min([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    max_point = Point(
        x=max([max([seg.start.x, seg.end.x]) for seg in edge_segments]),
        y=max([max([seg.start.y, seg.end.y]) for seg in edge_segments]),
    )
    width = max_point.x - min_point.x + 1
    height = max_point.y - min_point.y + 1
    char_buffer: list[list[str | None]] = list()
    for y in range(height):
        char_buffer.append(list([None] * width))
    offset_edge_segments = [
        EdgeSegment(
            start=Point(
                edge_segment.start.x - min_point.x, edge_segment.start.y - min_point.y
            ),
            end=Point(
                edge_segment.end.x - min_point.x, edge_segment.end.y - min_point.y
            ),
        )
        for edge_segment in edge_segments
    ]
    last_segment: EdgeSegment | None = None
    for edge_segment in offset_edge_segments:
        start, end = edge_segment.start, edge_segment.end
        first_character = True
        if edge_segment.vertical:
            for y in edge_segment.vertical_range():
                if (
                    first_character
                    and last_segment is not None
                    and last_segment.horizontal
                ):
                    if last_segment.start.x < start.x:
                        if end.y > last_segment.end.y:
                            char_buffer[y][start.x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_UPPER_RIGHT
                            ]
                        else:
                            char_buffer[y][start.x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_LOWER_RIGHT
                            ]
                    else:
                        if end.y > last_segment.end.y:
                            char_buffer[y][start.x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_UPPER_LEFT
                            ]
                        else:
                            char_buffer[y][start.x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_LOWER_LEFT
                            ]
                else:
                    char_buffer[y][start.x] = edge_characters[drawing_mode][
                        EdgeCharacters.VERTICAL
                    ]
                first_character = False
        elif edge_segment.horizontal:
            for x in edge_segment.horizontal_range():
                if (
                    first_character
                    and last_segment is not None
                    and last_segment.vertical
                ):
                    if last_segment.start.y > start.y:
                        if end.x < last_segment.end.x:
                            char_buffer[start.y][x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_UPPER_RIGHT
                            ]
                        else:
                            char_buffer[start.y][x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_UPPER_LEFT
                            ]
                    else:
                        if end.x < last_segment.end.x:
                            char_buffer[start.y][x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_LOWER_RIGHT
                            ]
                        else:
                            char_buffer[start.y][x] = edge_characters[drawing_mode][
                                EdgeCharacters.CORNER_LOWER_LEFT
                            ]
                else:
                    char_buffer[start.y][x] = edge_characters[drawing_mode][
                        EdgeCharacters.HORIZONTAL
                    ]
                first_character = False

        last_segment = edge_segment

    return [
        Strip(
            [
                Segment(text=character, style=style)
                if character is not None
                else Spacer(width=1)
                for character in line
            ]
        )
        for line in char_buffer
    ]
