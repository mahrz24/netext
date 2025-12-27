import itertools
import sys
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.edge import EdgePath
from netext._core import Direction
from netext.rendering.segment_buffer import Spacer, Strip
from rich.segment import Segment
from rich.style import Style

box_character_map = {
    EdgeSegmentDrawingMode.BOX: [
        "│",
        "─",
        "└",
        "┘",
        "┌",
        "┐",
        "/",
        "\\",
    ],
    EdgeSegmentDrawingMode.BOX_ROUNDED: [
        "│",
        "─",
        "╰",
        "╯",
        "╭",
        "╮",
        "/",
        "\\",
    ],
    EdgeSegmentDrawingMode.BOX_DOUBLE: [
        "║",
        "═",
        "╚",
        "╝",
        "╔",
        "╗",
        "/",
        "\\",
    ],
    EdgeSegmentDrawingMode.BOX_HEAVY: [
        "┃",
        "━",
        "┗",
        "┛",
        "┏",
        "┓",
        "/",
        "\\",
    ],
    EdgeSegmentDrawingMode.ASCII: [
        "|",
        "-",
        "+",
        "+",
        "+",
        "+",
        "/",
        "\\",
    ],
}


def rasterize_point(
    directions: list[Direction], style: Style, edge_segment_drawing_mode: EdgeSegmentDrawingMode
) -> Segment:
    if edge_segment_drawing_mode in [
        EdgeSegmentDrawingMode.BOX,
        EdgeSegmentDrawingMode.BOX_ROUNDED,
        EdgeSegmentDrawingMode.BOX_DOUBLE,
        EdgeSegmentDrawingMode.BOX_HEAVY,
        EdgeSegmentDrawingMode.ASCII,
    ]:
        first = directions[0]
        last = directions[-1]
        if (
            first == Direction.UP
            and (last == Direction.DOWN or last == Direction.UP)
            or first == Direction.DOWN
            and (last == Direction.UP or last == Direction.DOWN)
        ):
            return Segment(box_character_map[edge_segment_drawing_mode][0], style=style)
        elif (
            first == Direction.LEFT
            and (last == Direction.RIGHT or last == Direction.LEFT)
            or first == Direction.RIGHT
            and (last == Direction.LEFT or last == Direction.RIGHT)
        ):
            return Segment(box_character_map[edge_segment_drawing_mode][1], style=style)
        elif (
            first == Direction.UP
            and (last == Direction.RIGHT or last == Direction.UP)
            or first == Direction.RIGHT
            and (last == Direction.UP or last == Direction.RIGHT)
        ):
            return Segment(box_character_map[edge_segment_drawing_mode][2], style=style)
        elif (
            first == Direction.UP
            and (last == Direction.LEFT or last == Direction.UP)
            or first == Direction.LEFT
            and (last == Direction.UP or last == Direction.LEFT)
        ):
            return Segment(box_character_map[edge_segment_drawing_mode][3], style=style)
        elif (
            first == Direction.DOWN
            and (last == Direction.RIGHT or last == Direction.DOWN)
            or first == Direction.RIGHT
            and (last == Direction.DOWN or last == Direction.RIGHT)
        ):
            return Segment(box_character_map[edge_segment_drawing_mode][4], style=style)
        elif (
            first == Direction.DOWN
            and (last == Direction.LEFT or last == Direction.DOWN)
            or first == Direction.LEFT
            and (last == Direction.DOWN or last == Direction.LEFT)
        ):
            return Segment(box_character_map[edge_segment_drawing_mode][5], style=style)
        elif Direction.UP_RIGHT in directions or Direction.DOWN_LEFT in directions:
            return Segment(box_character_map[edge_segment_drawing_mode][6], style=style)
        elif Direction.UP_LEFT in directions or Direction.DOWN_RIGHT in directions:
            return Segment(box_character_map[edge_segment_drawing_mode][7], style=style)
    return Segment("*", style=style)


def rasterize_edge_path(
    path: EdgePath, style: Style, edge_segment_drawing_mode: EdgeSegmentDrawingMode, dash_pattern: list[int] | None
) -> list[Strip]:
    # Convert path to characters and points using the specified drawing mode
    character_path = []
    directions = []
    current_point = path.directed_points[0].point

    pattern = itertools.cycle(dash_pattern or [len(path.distinct_points)])

    pen_down = True
    offset = next(pattern)
    debug = False

    for directed_point in path.directed_points:
        if directed_point.point == current_point:
            directions.append(directed_point.direction)
            if directed_point.debug:
                debug = True
        else:
            if pen_down:
                segment = rasterize_point(directions, style, edge_segment_drawing_mode)
            else:
                segment = Spacer(width=1)

            if debug:
                if isinstance(segment, Spacer):
                    segment = Segment(" ", style=Style(bgcolor="red"))
                else:
                    [segment] = Segment.apply_style([segment], Style(bgcolor="red"))
            offset -= 1
            character_path.append((current_point, segment))

            if offset == 0:
                pen_down = not pen_down
                offset = next(pattern)

            current_point = directed_point.point
            debug = directed_point.debug
            directions = [directed_point.direction]

    character_path.append((current_point, rasterize_point(directions, style, edge_segment_drawing_mode)))
    assert len(character_path) == len(path.distinct_points)
    strips = []
    # Create a map of the points y coordinates to a list of points sorted by the x coordinate
    y_to_x = {}
    coord_to_segment = {}
    min_x = sys.maxsize
    max_x = -sys.maxsize
    for point, segment in character_path:
        if point.y not in y_to_x:
            y_to_x[point.y] = []
        if point.x not in y_to_x[point.y]:
            y_to_x[point.y].append(point.x)
            coord_to_segment[(point.x, point.y)] = segment
        min_x = min(min_x, point.x)
        max_x = max(max_x, point.x)
    # Sort the x coordinates
    for y in y_to_x.keys():
        y_to_x[y] = sorted(y_to_x[y])
    # Get the y bounds
    min_y = min(y_to_x.keys())
    max_y = max(y_to_x.keys())
    # Create the strips
    for y in range(min_y, max_y + 1):
        segments: list[Spacer | Segment] = []
        if y not in y_to_x:
            strips.append(Strip([Spacer(max_x - min_x + 1)]))
            continue
        x_coords = y_to_x[y]

        last_x = min_x - 1
        x = min_x
        for x in x_coords:
            if x - last_x > 1:
                segments.append(Spacer(x - last_x - 1))
            if x != last_x or x == min_x:
                segments.append(coord_to_segment[(x, y)])
            last_x = x
        if x < max_x and x - last_x > 0:
            segments.append(Spacer(max_x - x - 1))
        strips.append(Strip(segments=segments))
    return strips
