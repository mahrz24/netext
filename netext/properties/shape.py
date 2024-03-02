from dataclasses import dataclass
from typing import Literal
from rich.box import Box as RichBox, ROUNDED


@dataclass
class ShapeProperties:
    shape_type: Literal["box", "just_content"]


@dataclass
class JustContent(ShapeProperties):
    shape_type: Literal["box", "just_content"] = "just_content"


@dataclass
class Box(ShapeProperties):
    shape_type: Literal["box", "just_content"] = "box"
    box_type: RichBox = ROUNDED
