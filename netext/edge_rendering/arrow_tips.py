from typing import Hashable
from rich.segment import Segment
from rich.style import Style
from netext._core import Direction, Point
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import EdgePath
from netext.properties.arrow_tips import ARROW_TIPS, ArrowDirections, ArrowTip
from netext.rendering.segment_buffer import Layer, Strip, StripBuffer, ZIndex





def render_arrow_tip_buffer(
    edge: tuple[Hashable, Hashable],
    arrow_tip: ArrowTip,
    arrow_tip_position: Point,
    arrow_tip_dir: Direction,
    edge_segment_drawing_mode: EdgeSegmentDrawingMode,
    style: Style | None = None,
) -> StripBuffer:
    match arrow_tip_dir:
        case Direction.UP:
            direction = ArrowDirections.UP
        case Direction.DOWN:
            direction = ArrowDirections.DOWN
        case Direction.LEFT:
            direction = ArrowDirections.LEFT
        case Direction.RIGHT:
            direction = ArrowDirections.RIGHT
        case Direction.UP_LEFT:
            direction = ArrowDirections.UP
        case Direction.UP_RIGHT:
            direction = ArrowDirections.UP
        case Direction.DOWN_LEFT:
            direction = ArrowDirections.DOWN
        case Direction.DOWN_RIGHT:
            direction = ArrowDirections.DOWN
        case _:
            direction = ArrowDirections.UP

    tip_character = ARROW_TIPS[arrow_tip][edge_segment_drawing_mode][direction]

    return EdgeBuffer(
        edge=edge,
        z_index=ZIndex(layer=Layer.EDGE_DECORATIONS),
        boundary_1=arrow_tip_position,
        boundary_2=arrow_tip_position,
        strips=[Strip([Segment(text=tip_character, style=style)])],
    )


def render_arrow_tip_buffers(
    edge: tuple[Hashable, Hashable],
    end_arrow_tip: ArrowTip | None,
    start_arrow_tip: ArrowTip | None,
    edge_path: EdgePath,
    edge_segment_drawing_mode: EdgeSegmentDrawingMode,
    style: Style | None = None,
) -> list[StripBuffer]:
    buffers: list[StripBuffer] = []

    start_arrow_tip_position, start_arrow_tip_dir  = edge_path.directed_points[1]

    if start_arrow_tip is not None and start_arrow_tip != ArrowTip.NONE:
        buffers.append(
            render_arrow_tip_buffer(
                edge,
                start_arrow_tip,
                start_arrow_tip_position,
                start_arrow_tip_dir,
                edge_segment_drawing_mode,
                style=style,
            )
        )

    end_arrow_tip_position, end_arrow_tip_dir = edge_path.directed_points[-2]

    if end_arrow_tip is not None and end_arrow_tip != ArrowTip.NONE:
        buffers.append(
            render_arrow_tip_buffer(
                edge,
                end_arrow_tip,
                end_arrow_tip_position,
                end_arrow_tip_dir,
                edge_segment_drawing_mode,
                style=style,
            )
        )

    return buffers
