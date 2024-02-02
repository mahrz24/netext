from dataclasses import dataclass
from rich.box import Box as RichBox, ROUNDED


@dataclass
class ShapeProperties:
    pass


@dataclass
class JustContentProperties(ShapeProperties):
    pass


@dataclass
class BoxProperties(ShapeProperties):
    box_type: RichBox = ROUNDED
