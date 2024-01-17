from dataclasses import dataclass
from netext.shapes.box import Box

from netext.shapes.shape import JustContent, Shape

from rich.box import Box as RichBox, ROUNDED


@dataclass
class ShapeProperties:
    shape_type: type[Shape] = Box


@dataclass
class JustContentProperties(ShapeProperties):
    shape_type: type[Shape] = JustContent


@dataclass
class BoxProperties(ShapeProperties):
    box_type: RichBox = ROUNDED
