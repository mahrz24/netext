from dataclasses import dataclass, field
from typing import Any, Union
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from rich.style import Style

from netext.properties.node import _get_allow_none_if_exists


@dataclass
class EdgeProperties:
    show: bool = True
    label: str | None = None
    style: Style = Style()

    routing_mode: EdgeRoutingMode = EdgeRoutingMode.STRAIGHT
    segment_drawing_mode: EdgeSegmentDrawingMode = EdgeSegmentDrawingMode.SINGLE_CHARACTER

    start_arrow_tip: ArrowTip | None = None
    end_arrow_tip: ArrowTip | None = None

    start_port: str | None = None
    end_port: str | None = None

    lod_properties: dict[int, "EdgeProperties"] = field(default_factory=dict)

    @classmethod
    def from_attribute_dict(
        cls,
        data: dict[str, Any],
        suffix: str = "",
        fallback: Union["EdgeProperties", None] = None,
    ) -> "EdgeProperties":
        fallback = fallback or cls()
        style: Style = _get_allow_none_if_exists(data, f"$style{suffix}", fallback.style)
        show: bool = _get_allow_none_if_exists(data, f"$show{suffix}", fallback.show)
        label: str | None = _get_allow_none_if_exists(data, f"$label{suffix}", fallback.label)
        routing_mode: EdgeRoutingMode = _get_allow_none_if_exists(
            data, f"$edge-routing-mode{suffix}", fallback.routing_mode
        )
        segment_drawing_mode: EdgeSegmentDrawingMode = _get_allow_none_if_exists(
            data, f"$edge-segment-drawing-mode{suffix}", fallback.segment_drawing_mode
        )
        start_arrow_tip: ArrowTip | None = _get_allow_none_if_exists(
            data, f"$start-arrow-tip{suffix}", fallback.start_arrow_tip
        )
        end_arrow_tip: ArrowTip | None = _get_allow_none_if_exists(
            data, f"$end-arrow-tip{suffix}", fallback.end_arrow_tip
        )
        start_port: str | None = _get_allow_none_if_exists(data, f"$start-port{suffix}", fallback.start_port)
        end_port: str | None = _get_allow_none_if_exists(data, f"$end-port{suffix}", fallback.end_port)

        lod_properties: dict[int, "EdgeProperties"] = dict()

        result = cls(
            style=style,
            show=show,
            label=label,
            routing_mode=routing_mode,
            segment_drawing_mode=segment_drawing_mode,
            start_arrow_tip=start_arrow_tip,
            end_arrow_tip=end_arrow_tip,
            start_port=start_port,
            end_port=end_port,
            lod_properties=lod_properties,
        )

        for key in data.keys():
            try:
                lod = int(key.removesuffix(suffix).split("-")[-1])
                if lod not in lod_properties:
                    lod_properties[lod] = cls.from_attribute_dict(data, f"-{lod}", result)
            except ValueError:
                continue

        return result
