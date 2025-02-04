from dataclasses import dataclass, field
from typing import Any, Callable, Union, cast
from netext.geometry.magnet import Magnet
from netext.properties.shape import Box, ShapeProperties
from rich.style import Style
from rich.padding import PaddingDimensions
from rich.text import Text
from rich.console import RenderableType


def remove_none_values(data: dict[str, Any]) -> dict[str, Any]:
    result_data = dict(**data)
    to_be_ignored = []
    for key, val in result_data.items():
        if val is None:
            to_be_ignored.append(key)
    for key in to_be_ignored:
        del result_data[key]
    return result_data


def _default_content_renderer(node_str: str, data: dict[str, Any], content_style: Style) -> RenderableType:
    return Text(node_str, style=content_style)


@dataclass
class Port:
    label: str = ""
    magnet: Magnet | None = None
    key: int = 0
    symbol: str = "○"
    symbol_connected: str = "●"
    offset: int | None = None

    @classmethod
    def parse(cls, value: Union[dict[str, Any], "Port"]) -> "Port":
        if isinstance(value, dict):
            label = value.get("label", "")
            key = value.get("key", 0)
            magnet = value.get("magnet")
            symbol = value.get("symbol", "○")
            symbol_connected = value.get("symbol_connected", "●")
            offset = value.get("offset")
            return cls(
                label=label, magnet=magnet, symbol=symbol, symbol_connected=symbol_connected, offset=offset, key=key
            )
        else:
            return value


@dataclass
class NodeProperties:
    shape: ShapeProperties = field(default_factory=Box)
    style: Style = Style()
    content_style: Style = Style()
    margin: int = 0
    padding: PaddingDimensions = (0, 1)
    content_renderer: Callable[[str, dict[str, Any], Style], RenderableType] = _default_content_renderer

    lod_map: Callable[[float], int] = lambda _: 1  # noqa: E731
    lod_properties: dict[int, "NodeProperties"] = field(default_factory=dict)
    ports: dict[str, Port] = field(default_factory=dict)
    slots: bool = False

    @classmethod
    def from_data_dict(cls, data: dict[str, Any]):
        cleaned_data = remove_none_values(data)
        return cast(NodeProperties, cleaned_data.get("$properties", cls.from_attribute_dict(cleaned_data)))

    @classmethod
    def from_attribute_dict(
        cls,
        data: dict[str, Any],
        suffix: str = "",
        fallback: Union["NodeProperties", None] = None,
    ) -> "NodeProperties":
        fallback = fallback or cls()
        shape: ShapeProperties = ShapeProperties.parse(data, suffix, fallback.shape)
        style: Style = data.get(f"$style{suffix}", fallback.style)
        content_style = data.get(f"$content-style{suffix}", fallback.content_style)
        margin: int = data.get(f"$margin{suffix}", fallback.margin)
        padding: PaddingDimensions = data.get(f"$padding{suffix}", fallback.padding)
        content_renderer = data.get(f"$content-renderer{suffix}", fallback.content_renderer)

        lod_map: Callable[[float], int] = data.get("$lod-map", fallback.lod_map)
        lod_properties: dict[int, "NodeProperties"] = dict()
        ports: dict[str, dict[str, Any] | Port] = data.get("$ports", dict())
        slots: bool = data.get("$slots", fallback.slots)

        result = cls(
            shape=shape,
            style=style,
            content_style=content_style,
            margin=margin,
            padding=padding,
            content_renderer=content_renderer,
            lod_map=lod_map,
            lod_properties=lod_properties,
            ports={k: Port.parse(v) for k, v in ports.items()},
            slots=slots,
        )

        # Load properies for all levels of detail
        lods = set()
        for key in data.keys():
            try:
                lods.add(int(key.removesuffix(suffix).split("-")[-1]))
            except ValueError:
                continue

        for lod in lods:
            lod_properties[lod] = cls.from_attribute_dict(data, f"-{lod}", result)

        result.lod_properties = lod_properties

        return result
