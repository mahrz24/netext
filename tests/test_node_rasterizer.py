import pytest
from rich.console import Console
from rich.segment import Segment
from rich.style import Style
from rich.text import Text

from netext.node_rasterizer import rasterize_node


@pytest.fixture
def console() -> Console:
    return Console()


def test_trivial_node(console: Console) -> None:
    node_buffer = rasterize_node(console, node="foo", data=dict())

    assert node_buffer.shape_width == 7
    assert node_buffer.shape_height == 3
    assert Segment("foo") in node_buffer.strips[1].segments


def test_trivial_node_with_style(console: Console) -> None:
    node_buffer = rasterize_node(console, node="foo", data={"$style": Style(color="red")})

    assert node_buffer.shape_width == 7
    assert node_buffer.shape_height == 3
    assert Segment("foo", style=Style(color="red")) in node_buffer.strips[1].segments


def test_trivial_node_with_style_and_text_style(console: Console) -> None:
    node_buffer = rasterize_node(
        console,
        node="foo",
        data={"$style": Style(color="red"), "$content-style": Style(color="green")},
    )

    assert node_buffer.shape_width == 7
    assert node_buffer.shape_height == 3
    assert Segment("foo", style=Style(color="green")) in node_buffer.strips[1].segments


def test_trivial_node_with_style_and_custom_renderer(console: Console) -> None:
    node_buffer = rasterize_node(
        console,
        node="foo",
        data={
            "$style": Style(color="red"),
            "$content-renderer": lambda str, _, __: Text(str.upper()),
        },
    )

    assert node_buffer.shape_width == 7
    assert node_buffer.shape_height == 3
    assert Segment("FOO", style=Style(color="red")) in node_buffer.strips[1].segments


def test_plain_shape(console: Console) -> None:
    node_buffer = rasterize_node(console, node="foo", data={"$shape": "just-content"})

    assert node_buffer.shape_width == 3
    assert node_buffer.shape_height == 1
    assert Segment("foo") in node_buffer.strips[0].segments
