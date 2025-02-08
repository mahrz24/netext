from importlib.util import find_spec
import rich_click as click
import sys
import json
import networkx as nx

from netext import ConsoleGraph, EdgeRoutingMode, EdgeSegmentDrawingMode
from rich import print


HAS_DOT = find_spec("pydot") is not None


@click.command()
@click.argument("file", type=click.File("r"), default=sys.stdin)
def run(file):
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
                    graphs.append(graph)
        else:
            click.echo("Could not parse JSON and pydot is not installed.")
    for graph in graphs:
        print(ConsoleGraph(graph))
