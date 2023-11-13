from netext.geometry.magnet import Magnet
from netext.layout_engines.static import StaticLayout
from netext.textual.widget import GraphView
from textual.app import App, ComposeResult
from rich.style import Style
from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
from netext.edge_rendering.arrow_tips import ArrowTip
from textual.screen import Screen
from textual.widgets import RadioSet
from textual.geometry import Size
from rich import box
import networkx as nx
from PIL import Image, ImageDraw
import math
from rich_pixels import Pixels
from rich.panel import Panel
from rich.console import Group
from rich.text import Text
from textual import on


def _render(n, d, s):
    # Generate a PIL image using the specified waveform of length 10 pixels
    # and height 1 pixel.
    # The image is then scaled up by a factor of 10 and rendered using the
    # JustContent node rasterizer.
    waveform = d["waveform"]
    width = 40
    frequency = 3
    image = Image.new("L", (width, 1))
    draw = ImageDraw.Draw(image)
    if waveform == "sine":
        for x in range(width):
            y = round((math.sin(x / width * frequency * 2 * math.pi) + 1) * 127)
            draw.point((x, 0), fill=y)
    elif waveform == "square":
        for x in range(width):
            y = (round(x / width * frequency) % 2) * 255
            draw.point((x, 0), fill=y)
    elif waveform == "sawtooth":
        for x in range(width):
            y = round(x / width * frequency * 255) % 255
            draw.point((x, 0), fill=y)

    return Group(
        Text(""),
        Text(""),
        Text(""),
        Text(""),
        Panel(
            Pixels.from_image(image),
            title="Preview",
            box=box.SQUARE,
            expand=False,
            width=width + 10,
            height=3,
            style="blue",
        ),
    )


def _render_composed(n, d, s):
    waveform_x = d["waveform-x"]
    waveform_y = d["waveform-y"]
    width = 40
    height = 25
    frequency = 3
    # Generate a PIL image that multiplicates the x and y values
    # of the corresponding waveforms.
    image = Image.new("L", (width, height))
    draw = ImageDraw.Draw(image)
    for x in range(width):
        for y in range(height):
            x_val = 0
            if waveform_x == "sine":
                x_val = round((math.sin(x / width * frequency * 2 * math.pi) + 1) * 127)
            elif waveform_x == "square":
                x_val = (round(x / width * frequency) % 2) * 255
            elif waveform_x == "sawtooth":
                x_val = round(x / width * frequency * 255) % 255

            y_val = 0
            if waveform_y == "sine":
                y_val = round(
                    (math.sin(y / height * frequency * 2 * math.pi) + 1) * 127
                )
            elif waveform_y == "square":
                y_val = (round(y / height * frequency) % 2) * 255
            elif waveform_y == "sawtooth":
                y_val = round(y / height * frequency * 255) % 255
            draw.point((x, y), fill=x_val * y_val // 255)

    return Panel(
        Pixels.from_image(image),
        title="Preview",
        box=box.SQUARE,
        expand=False,
        width=width + 10,
        height=height + 2,
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
    "XY Compose",
    **{
        "$x": 90,
        "$y": 10,
        "$content-renderer": _render_composed,
        "waveform-x": "sine",
        "waveform-y": "sine",
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
        self.set_timer(0.1, self.attach)

    def attach(self):
        s = RadioSet("sine", "square", "sawtooth", id="waveform-1")
        s.focus()
        graph_view = self.query_one(GraphView)
        graph_view.attach_widget_to_node(s, "Wave 1", size=Size(20, 4))

        s = RadioSet("sine", "square", "sawtooth", id="waveform-2")
        s.focus()
        graph_view = self.query_one(GraphView)
        graph_view.attach_widget_to_node(s, "Wave 2", size=Size(20, 4))

    @on(RadioSet.Changed, "#waveform-1")
    def waveform_1_changed(self, event: RadioSet.Changed):
        graph_view = self.query_one(GraphView)
        graph_view.update_node("Wave 1", data={"waveform": str(event.pressed.label)})
        graph_view.update_node(
            "XY Compose", data={"waveform-x": str(event.pressed.label)}
        )

    @on(RadioSet.Changed, "#waveform-2")
    def waveform_2_changed(self, event: RadioSet.Changed):
        graph_view = self.query_one(GraphView)
        graph_view.update_node("Wave 2", data={"waveform": str(event.pressed.label)})
        graph_view.update_node(
            "XY Compose", data={"waveform-y": str(event.pressed.label)}
        )


class GraphApp(App):
    CSS_PATH = "compose.css"

    def on_mount(self):
        self.push_screen(MainScreen())


app = GraphApp()

app.run()
