import math

from typing import cast

from rich.console import Console, RenderableType
from rich.padding import PaddingDimensions, Padding
from rich.style import Style
from rich.panel import Panel

from netext.geometry.magnet import ShapeSide
from netext.properties.shape import Box, ShapeProperties

from netext.rendering.segment_buffer import Strip
from netext.shapes.shape import RectangularShapeMixin


class BoxShape(RectangularShapeMixin):
    def render_shape(
        self,
        console: Console,
        width: int | None,
        height: int | None,
        content_renderable: RenderableType,
        style: Style,
        padding: PaddingDimensions,
        properties: ShapeProperties,
        port_side_assignments: dict[ShapeSide, list[str]] = dict(),
    ) -> list[Strip]:
        properties = cast(Box, properties)

        padding = Padding.unpack(padding)

        # Measure content
        result = self._renderable_type_to_strips(
            console,
            Panel(
                content_renderable,
                expand=False,
                width=width,
                height=height,
                style=style,
                padding=padding,
                box=properties.box_type,
            ),
        )

        height = len(result)
        width = max(sum([segment.cell_length for segment in strip.segments]) for strip in result)
        rerender = False

        if port_side_assignments:
            if (
                missing_space := width
                - 2
                - max(
                    len(port_side_assignments.get(ShapeSide.TOP, [])),
                    len(port_side_assignments.get(ShapeSide.BOTTOM, [])),
                )
            ) < 0:
                additional_padding = int(math.ceil(-missing_space / 2))
                padding = (
                    padding[0],
                    padding[1] + additional_padding,
                    padding[2],
                    padding[3] + additional_padding,
                )
                rerender = True

            if (
                missing_space := height
                - 2
                - max(
                    len(port_side_assignments.get(ShapeSide.LEFT, [])),
                    len(port_side_assignments.get(ShapeSide.RIGHT, [])),
                )
            ) < 0:
                additional_padding = int(math.ceil(-missing_space / 2))
                padding = (
                    padding[0] + additional_padding,
                    padding[1],
                    padding[2] + additional_padding,
                    padding[3],
                )
                rerender = True

        if rerender:
            result = self._renderable_type_to_strips(
                console,
                Panel(
                    content_renderable,
                    expand=False,
                    style=style,
                    padding=padding,
                    box=properties.box_type,
                ),
            )

        return result
