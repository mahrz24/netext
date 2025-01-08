from enum import Enum
from netext.edge_rendering.modes import EdgeSegmentDrawingMode

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
        }
    }
}
