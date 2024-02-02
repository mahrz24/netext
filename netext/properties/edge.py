from dataclasses import dataclass
from typing import Any, Union
from netext.edge_rendering.arrow_tips import ArrowTip
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from rich.style import Style


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

    lod_properties: dict[int, "EdgeProperties"] = dict()

    @classmethod
    def from_attribute_dict(
        cls,
        data: dict[str, Any],
        suffix: str = "",
        fallback: Union["EdgeProperties", None] = None,
    ) -> "EdgeProperties":
        fallback = fallback or cls()
        style: Style = data.get(f"$style{suffix}", fallback.style)
        show: bool = data.get(f"$show{suffix}", fallback.show)
        label: str | None = data.get(f"$label{suffix}", fallback.label)
        routing_mode: EdgeRoutingMode = data.get(f"$edge-routing-mode{suffix}", fallback.routing_mode)
        segment_drawing_mode: EdgeSegmentDrawingMode = data.get(
            f"$edge-segment-drawing-mode{suffix}", fallback.segment_drawing_mode
        )
        start_arrow_tip: ArrowTip | None = data.get(f"$start-arrow-tip{suffix}", fallback.start_arrow_tip)
        end_arrow_tip: ArrowTip | None = data.get(f"$end-arrow-tip{suffix}", fallback.end_arrow_tip)
        start_port: str | None = data.get(f"$start-port{suffix}", fallback.start_port)
        end_port: str | None = data.get(f"$end-port{suffix}", fallback.end_port)

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

        for lod, lod_data in data.get("$lod-properties", dict()).items():
            result.lod_properties[int(lod)] = cls.from_attribute_dict(lod_data, suffix, result)

        return result
