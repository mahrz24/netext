from enum import Enum
from rich.segment import Segment
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import RoutedEdgeSegments
from netext.geometry import Point
from netext.rendering.segment_buffer import Strip, StripBuffer


class ArrowTip(Enum):
    arrow = "arrow"


class ArrowDirections(Enum):
    left = "left"
    right = "right"
    up = "up"
    down = "down"


ARROW_TIPS = {
    ArrowTip.arrow: {
        EdgeSegmentDrawingMode.box: {
            ArrowDirections.left: "←",
            ArrowDirections.right: "→",
            ArrowDirections.up: "↑",
            ArrowDirections.down: "↓",
        },
        EdgeSegmentDrawingMode.single_character: {
            ArrowDirections.left: "<",
            ArrowDirections.right: ">",
            ArrowDirections.up: "^",
            ArrowDirections.down: "v",
        },
        EdgeSegmentDrawingMode.block: {
            ArrowDirections.left: "🭮",
            ArrowDirections.right: "🭬",
            ArrowDirections.up: "🭯",
            ArrowDirections.down: "🭭",
        },
        EdgeSegmentDrawingMode.braille: {
            ArrowDirections.left: "🭮",
            ArrowDirections.right: "🭬",
            ArrowDirections.up: "🭯",
            ArrowDirections.down: "🭭",
        },
    }
}


def render_arrow_tip_buffer(
    arrow_tip: ArrowTip,
    arrow_tip_position: Point,
    arrow_tip_dir: Point,
    edge_segment_drawing_mode: EdgeSegmentDrawingMode,
) -> StripBuffer:
    tangent = arrow_tip_dir - arrow_tip_position

    if abs(tangent.x) > abs(tangent.y):
        if tangent.x > 0:
            direction = ArrowDirections.left
        else:
            direction = ArrowDirections.right
    else:
        if tangent.y > 0:
            direction = ArrowDirections.up
        else:
            direction = ArrowDirections.down

    tip_character = ARROW_TIPS[arrow_tip][edge_segment_drawing_mode][direction]

    return EdgeBuffer(
        z_index=-1,
        boundary_1=arrow_tip_position,
        boundary_2=arrow_tip_position,
        strips=[Strip([Segment(text=tip_character)])],
    )


def render_arrow_tip_buffers(
    end_arrow_tip: ArrowTip | None,
    start_arrow_tip: ArrowTip | None,
    edge_segments: RoutedEdgeSegments,
    edge_segment_drawing_mode: EdgeSegmentDrawingMode,
) -> list[StripBuffer]:
    buffers: list[StripBuffer] = []

    start_arrow_tip_position = edge_segments.edge_iter_point(0)
    start_arrow_tip_dir = edge_segments.edge_iter_point(1)

    if start_arrow_tip is not None:
        buffers.append(
            render_arrow_tip_buffer(
                start_arrow_tip,
                start_arrow_tip_position,
                start_arrow_tip_dir,
                edge_segment_drawing_mode,
            )
        )

    end_arrow_tip_position = edge_segments.edge_iter_point(-1)
    end_arrow_tip_dir = edge_segments.edge_iter_point(-2)

    if end_arrow_tip is not None:
        buffers.append(
            render_arrow_tip_buffer(
                end_arrow_tip,
                end_arrow_tip_position,
                end_arrow_tip_dir,
                edge_segment_drawing_mode,
            )
        )

    return buffers
