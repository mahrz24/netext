from dataclasses import dataclass, field
from typing import Any, Callable, Union, cast
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_routing.modes import EdgeRoutingMode
from rich.style import Style
from netext.geometry.magnet import Magnet

from netext.properties.arrow_tips import ArrowTip
from netext.properties.node import remove_none_values


@dataclass
class EdgeProperties:
    show: bool = True
    label: str | None = None
    style: Style = Style()
    dash_pattern: list[int] | None = None

    routing_mode: EdgeRoutingMode = EdgeRoutingMode.STRAIGHT
    segment_drawing_mode: EdgeSegmentDrawingMode = EdgeSegmentDrawingMode.SINGLE_CHARACTER

    start_arrow_tip: ArrowTip | None = None
    end_arrow_tip: ArrowTip | None = None


    start_port: str | None = None
    end_port: str | None = None

    start_magnet: Magnet = Magnet.CLOSEST
    end_magnet: Magnet = Magnet.CLOSEST

    lod_map: Callable[[float], int] = lambda _: 1  # noqa: E731
    lod_properties: dict[int, "EdgeProperties"] = field(default_factory=dict)

    @classmethod
    def from_data_dict(cls, data: dict[str, Any]):
        cleaned_data = remove_none_values(data)
        return cast(EdgeProperties, cleaned_data.get("$properties", cls.from_attribute_dict(cleaned_data)))

    @classmethod
    def from_attribute_dict(
        cls,
        data: dict[str, Any],
        suffix: str = "",
        fallback: Union["EdgeProperties", None] = None,
    ) -> "EdgeProperties":
        fallback = fallback or cls()
        style: Style = data.get(f"$style{suffix}", fallback.style)
        dash_pattern: list[int] | None = data.get(f"$dash-pattern{suffix}", fallback.dash_pattern)
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
        start_magnet: Magnet = data.get(f"$start-magnet{suffix}", fallback.start_magnet)
        end_magnet: Magnet = data.get(f"$end-magnet{suffix}", fallback.end_magnet)

        lod_map: Callable[[float], int] = data.get("$lod-map", fallback.lod_map)
        lod_properties: dict[int, "EdgeProperties"] = dict()

        result = cls(
            style=style,
            dash_pattern=dash_pattern,
            show=show,
            label=label,
            routing_mode=routing_mode,
            segment_drawing_mode=segment_drawing_mode,
            start_arrow_tip=start_arrow_tip,
            end_arrow_tip=end_arrow_tip,
            start_port=start_port,
            end_port=end_port,
            start_magnet=start_magnet,
            end_magnet=end_magnet,
            lod_map=lod_map,
            lod_properties=lod_properties,
        )

        for key in data.keys():
            try:
                lod = int(key.removesuffix(suffix).split("-")[-1])
                if lod not in lod_properties:
                    lod_properties[lod] = cls.from_attribute_dict(data, f"-{lod}", result)
            except ValueError:
                continue

        result.lod_properties = lod_properties

        return result
