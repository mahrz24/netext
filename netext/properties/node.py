from dataclasses import dataclass, field
from typing import Any, Callable, Union
from netext.shapes.shape import Shape
from netext.shapes.box import Box
from rich.style import Style
from rich.padding import PaddingDimensions
from rich.text import Text
from rich.console import RenderableType


def _default_content_renderer(node_str: str, data: dict[str, Any], content_style: Style) -> RenderableType:
    return Text(node_str, style=content_style)


@dataclass
class NodeProperties:
    shape: Shape = Box()
    style: Style = Style()
    content_style: Style = Style()
    margin: int = 0
    padding: PaddingDimensions = (0, 1)
    content_renderer: Callable[[str, dict[str, Any], Style], RenderableType] = _default_content_renderer
    lod_properties: dict[int, "NodeProperties"] = field(default_factory=dict)

    @classmethod
    def from_attribute_dict(
        cls,
        data: dict[str, Any],
        suffix: str = "",
        fallback: Union["NodeProperties", None] = None,
    ) -> "NodeProperties":
        fallback = fallback or cls()
        shape: Shape = data.get(f"$shape{suffix}", fallback.shape)
        style: Style = data.get(f"$style{suffix}", fallback.style)
        content_style = data.get(f"$content-style{suffix}", fallback.content_style)
        margin: int = data.get(f"$margin{suffix}", fallback.margin)
        padding: PaddingDimensions = data.get(f"$padding{suffix}", fallback.padding)
        content_renderer = data.get(f"$content-renderer{suffix}", fallback.content_renderer)
        lod_properties: dict[int, "NodeProperties"] = dict()

        result = cls(
            shape=shape,
            style=style,
            content_style=content_style,
            margin=margin,
            padding=padding,
            content_renderer=content_renderer,
            lod_properties=lod_properties,
        )

        # Load properies for all levels of detail
        for key in data.keys():
            try:
                lod = int(key.removesuffix(suffix).split("-")[-1])
                if lod not in lod_properties:
                    lod_properties[lod] = cls.from_attribute_dict(data, f"-{lod}", result)
            except ValueError:
                continue

        result.lod_properties = lod_properties

        return result
