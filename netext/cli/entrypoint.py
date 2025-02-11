from importlib.util import find_spec
from math import floor
import rich_click as click
import sys
import json
import networkx as nx

from netext import ConsoleGraph, EdgeRoutingMode, EdgeSegmentDrawingMode
from netext.cli.x11_colors import parse_x11_color
from rich import print
from rich.style import Style
from rich.text import Text
from rich.markdown import Markdown
from markdownify import markdownify as md

from netext._core import LayoutDirection, SugiyamaLayout


HAS_DOT = find_spec("pydot") is not None


@click.command()
@click.argument("file", type=click.File("r"), default=sys.stdin)
@click.option("--top-down/--left-right", default=True, help="Render the graph top-down or left-right.")
def run(file, top_down):
    """Render a graph from a JSON file or DOT file in the terminal."""
    file_content = file.read()
    graphs = []
    try:
        json_data = json.loads(file_content)
        # Assume a very simple JSON format mapping node names to lists of
        # neighbors and create a networkx graph from it
        graph = nx.Graph()
        for node, neighbors in json_data.items():
            for neighbor in neighbors:
                graph.add_edge(node, neighbor)
        graphs.append(graph)
    except json.JSONDecodeError:
        if HAS_DOT:
            from pydot import graph_from_dot_data

            dots = graph_from_dot_data(file_content)
            if dots:
                for dot in dots:
                    graph = nx.DiGraph(nx.nx_pydot.from_pydot(dot))
                    nx.set_edge_attributes(graph, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
                    nx.set_edge_attributes(graph, EdgeSegmentDrawingMode.BOX, "$edge-segment-drawing-mode")
                    convert_dot_attributes(graph)
                    graphs.append(graph)
        else:
            click.echo("Could not parse JSON and pydot is not installed.")
    layout_engine = SugiyamaLayout(direction=LayoutDirection.TOP_DOWN if top_down else LayoutDirection.LEFT_RIGHT)
    for graph in graphs:
        print(ConsoleGraph(graph, layout_engine=layout_engine))


def convert_dot_attributes(graph):
    for n, data in graph.nodes(data=True):
        bgcolor = None
        color = None
        fontcolor = None
        for key in data.keys():
            match key:
                case "fillcolor":
                    bgcolor = parse_x11_color(data[key])
                case "color":
                    color = parse_x11_color(data[key])
                case "fontcolor":
                    fontcolor = parse_x11_color(data[key])
                case "label":
                    data["label"] = md(data["label"])
        if bgcolor is not None and color is None:
            color = "black"
        if bgcolor is not None and fontcolor is None:
            fontcolor = "black"
        style = Style(bgcolor=bgcolor, color=color)

        def _render_node(n, d, s):
            if "label" not in d:
                return Text(n, style=s)
            label = d["label"]
            return Markdown(label, style=s)

        label = data.get("label", n) or n
        markdown_width = max([len(line) for line in label.split("\n")])

        # Just some heuristic to make the nodes a bit wider
        graph.nodes[n]["$width"] = floor(markdown_width * 1.5) + 4
        graph.nodes[n]["$style"] = style
        graph.nodes[n]["$content-renderer"] = _render_node
        graph.nodes[n]["$content-style"] = Style(bgcolor=bgcolor, color=fontcolor)
