from dataclasses import dataclass
from typing import Any, Callable
from netext.node_rasterizer import Shape, Box
from rich.style import Style
from rich.padding import PaddingDimensions
from rich.text import Text
from rich.console import RenderableType


def _default_content_renderer(
    node_str: str, data: dict[str, Any], content_style: Style
) -> RenderableType:
    return Text(node_str, style=content_style)


@dataclass
class NodeProperties:
    shape: Shape = Box()
    style: Style = Style()
    content_style: Style = Style()
    margin: int = 0
    padding: PaddingDimensions = (0, 1)
    content_renderer: Callable[
        [str, dict[str, Any], Style], RenderableType
    ] = _default_content_renderer
