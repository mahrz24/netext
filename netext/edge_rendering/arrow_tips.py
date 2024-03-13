from enum import Enum
from typing import Hashable
from rich.segment import Segment
from rich.style import Style
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.buffer import EdgeBuffer
from netext.edge_routing.edge import EdgePath
from netext.geometry import Point
from netext.rendering.segment_buffer import Layer, Strip, StripBuffer, ZIndex


class ArrowTip(Enum):
    ARROW = "arrow"
    NONE = "none"


class ArrowDirections(Enum):
    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


ARROW_TIPS = {
    ArrowTip.ARROW: {
        EdgeSegmentDrawingMode.BOX: {
            ArrowDirections.LEFT: "◀",
            ArrowDirections.RIGHT: "▶",
            ArrowDirections.UP: "▲",
            ArrowDirections.DOWN: "▼",
        },
        EdgeSegmentDrawingMode.BOX_ROUNDED: {
            ArrowDirections.LEFT: "◀",
            ArrowDirections.RIGHT: "▶",
            ArrowDirections.UP: "▲",
            ArrowDirections.DOWN: "▼",
        },
        EdgeSegmentDrawingMode.BOX_HEAVY: {
            ArrowDirections.LEFT: "◀",
            ArrowDirections.RIGHT: "▶",
            ArrowDirections.UP: "▲",
            ArrowDirections.DOWN: "▼",
        },
        EdgeSegmentDrawingMode.BOX_DOUBLE: {
            ArrowDirections.LEFT: "◀",
            ArrowDirections.RIGHT: "▶",
            ArrowDirections.UP: "▲",
            ArrowDirections.DOWN: "▼",
        },
        EdgeSegmentDrawingMode.SINGLE_CHARACTER: {
            ArrowDirections.LEFT: "<",
            ArrowDirections.RIGHT: ">",
            ArrowDirections.UP: "^",
            ArrowDirections.DOWN: "v",
        },
        EdgeSegmentDrawingMode.ASCII: {
            ArrowDirections.LEFT: "<",
            ArrowDirections.RIGHT: ">",
            ArrowDirections.UP: "^",
            ArrowDirections.DOWN: "v",
        },
        EdgeSegmentDrawingMode.BLOCK: {
            ArrowDirections.LEFT: "🭮",
            ArrowDirections.RIGHT: "🭬",
            ArrowDirections.UP: "🭯",
            ArrowDirections.DOWN: "🭭",
        },
        EdgeSegmentDrawingMode.BRAILLE: {
            ArrowDirections.LEFT: "🭮",
            ArrowDirections.RIGHT: "🭬",
            ArrowDirections.UP: "🭯",
            ArrowDirections.DOWN: "🭭",
        },
    }
}


def render_arrow_tip_buffer(
    edge: tuple[Hashable, Hashable],
    arrow_tip: ArrowTip,
    arrow_tip_position: Point,
    arrow_tip_dir: Point,
    edge_segment_drawing_mode: EdgeSegmentDrawingMode,
    style: Style | None = None,
) -> StripBuffer:
    tangent = arrow_tip_dir - arrow_tip_position

    if abs(tangent.x) > abs(tangent.y):
        if tangent.x > 0:
            direction = ArrowDirections.LEFT
        else:
            direction = ArrowDirections.RIGHT
    else:
        if tangent.y > 0:
            direction = ArrowDirections.UP
        else:
            direction = ArrowDirections.DOWN

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

    start_arrow_tip_position = edge_path.edge_iter_point(0)
    start_arrow_tip_dir = edge_path.edge_iter_point(1)

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

    end_arrow_tip_position = edge_path.edge_iter_point(-1)
    end_arrow_tip_dir = edge_path.edge_iter_point(-2)

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
