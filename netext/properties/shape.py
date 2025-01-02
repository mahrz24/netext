from dataclasses import dataclass
from typing import Any, Literal
from rich.box import Box as RichBox, ROUNDED


@dataclass
class ShapeProperties:
    shape_type: Literal["box", "just_content"]

    @classmethod
    def parse(cls, value: dict[str, Any], suffix: str, fallback: "ShapeProperties") -> "ShapeProperties":
        shape_type = value.get(f"$shape{suffix}", fallback.shape_type)
        match shape_type:
            case "box":
                return Box.parse(value, suffix, fallback)
            case "just-content":
                return JustContent()
            case _:
                raise ValueError(f"Unknown shape type: {shape_type}")


@dataclass
class JustContent(ShapeProperties):
    shape_type: Literal["box", "just_content"] = "just_content"


@dataclass
class Box(ShapeProperties):
    shape_type: Literal["box", "just_content"] = "box"
    box_type: RichBox = ROUNDED

    @classmethod
    def parse(cls, value: dict[str, Any], suffix: str, fallback: "ShapeProperties") -> "Box":
        assert isinstance(fallback, Box)
        box_type = value.get(f"$box-type{suffix}", fallback.box_type)
        match box_type:
            case "rounded":
                return Box(box_type=ROUNDED)
            case RichBox():
                return Box(box_type=box_type)
            case _:
                raise ValueError(f"Unknown box type: {box_type}")
