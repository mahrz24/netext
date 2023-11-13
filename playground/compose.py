from netext.geometry.magnet import Magnet
from netext.layout_engines.static import StaticLayout
from netext.textual.widget import GraphView
from textual.app import App, ComposeResult
from rich.style import Style
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.screen import Screen
from rich import box
import networkx as nx
from PIL import Image, ImageDraw
import math
from rich_pixels import Pixels
from rich.panel import Panel


def _render(n, d, s):
    # Generate a PIL image using the specified waveform of length 10 pixels
    # and height 1 pixel.
    # The image is then scaled up by a factor of 10 and rendered using the
    # JustContent node rasterizer.
    waveform = d["waveform"]
    width = 20
    image = Image.new("L", (width, 1))
    draw = ImageDraw.Draw(image)
    if waveform == "sine":
        for x in range(width):
            y = round((math.sin(x / width * 2 * math.pi) + 1) * 127)
            draw.point((x, 0), fill=y)
    elif waveform == "square":
        for x in range(width):
            draw.point((x, 0), fill=255)
    elif waveform == "sawtooth":
        for x in range(width):
            y = round(x / width * 255)
            draw.point((x, 0), fill=y)
    elif waveform == "triangle":
        for x in range(width):
            y = round(abs(2 * (x / width) - 1) * 255)
            draw.point((x, 0), fill=y)
    return Panel(
        Pixels.from_image(image),
        title="Preview",
        box=box.SQUARE,
        expand=False,
        width=width + 10,
        height=3,
        style="blue",
    )


g = nx.Graph()
g.add_node(
    "Wave 1",
    **{
        "$x": 5,
        "$y": 1,
        "waveform": "sine",
        "$content-renderer": _render,
        "$ports": {
            "out": {
                "magnet": Magnet.RIGHT,
                "label": "OUT",
            },
        },
    },
)

g.add_node(
    "Wave 2",
    **{
        "$x": 5,
        "$y": 20,
        "waveform": "triangle",
        "$content-renderer": _render,
        "$ports": {
            "out": {
                "magnet": Magnet.RIGHT,
                "label": "OUT",
            },
        },
    },
)

g.add_node(
    "XY Compose",
    **{
        "$x": 30,
        "$y": 10,
        "$ports": {
            "xin": {
                "magnet": Magnet.LEFT,
                "label": "X IN",
            },
            "yin": {
                "magnet": Magnet.LEFT,
                "label": "Y IN",
            },
        },
    },
)

g.add_edge(
    "Wave 1",
    "XY Compose",
    **{
        "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
        "$start-port": "out",
        "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
        "$end-arrow-tip": ArrowTip.ARROW,
        "$end-port": "xin",
        "$style": Style(color="green"),
    },
)

g.add_edge(
    "Wave 2",
    "XY Compose",
    **{
        "$edge-routing-mode": EdgeRoutingMode.ORTHOGONAL,
        "$start-port": "out",
        "$edge-segment-drawing-mode": EdgeSegmentDrawingMode.BOX,
        "$end-arrow-tip": ArrowTip.ARROW,
        "$end-port": "yin",
        "$style": Style(color="green"),
    },
)


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        graph_view = GraphView(
            g,
            zoom=1,
            scroll_via_viewport=False,
            id="graph",
            layout_engine=StaticLayout(),
        )
        yield graph_view


class GraphApp(App):
    CSS_PATH = "compose.css"

    def on_mount(self):
        self.push_screen(MainScreen())


app = GraphApp()

app.run()
