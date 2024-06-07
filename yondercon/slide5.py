from netext import ConsoleGraph
from rich import print
from rich.style import Style
from rich.text import Text

from netext.edge_routing.modes import EdgeRoutingMode
from netext.edge_rendering.modes import EdgeSegmentDrawingMode
import networkx as nx


def _render(n, d, s):
    return Text(str(d["label"]), style="blue")


G = nx.DiGraph()

G.add_node(0, label="Bread dough has been made.")
G.add_node(1, label="All starter depleted?")

G.add_node(2, label="Take around 10g of your bread dough.")
G.add_node(3, label="Take all but not more then 10g of your starter.")

G.add_node(4, label="Feed again with 50g of flour, 25g of water")

G.add_node(5, label="Baking next day?")

G.add_node(6, label="Make bread dough again after 8-12 hours.")

G.add_node(7, label="Baking in next 2 weeks?")

G.add_node(8, label="Store starter in fridge at 4 degrees C.")

G.add_node(9, label="Feed starter every 2 weeks or freeze it.")

G.add_edge(0, 1)

G.add_edge(1, 2, **{"$label": "Yes"})
G.add_edge(1, 3, **{"$label": "No"})

G.add_edge(2, 4)
G.add_edge(3, 4)

G.add_edge(4, 5)
G.add_edge(5, 6, **{"$label": "Yes"})
G.add_edge(5, 7, **{"$label": "No"})

G.add_edge(7, 8)
G.add_edge(7, 9)

nx.set_node_attributes(G, _render, "$content-renderer")
nx.set_node_attributes(G, Style(color="blue", bold=True), "$content-style")
nx.set_node_attributes(G, Style(color="green"), "$style")

nx.set_edge_attributes(G, EdgeRoutingMode.ORTHOGONAL, "$edge-routing-mode")
nx.set_edge_attributes(G, EdgeSegmentDrawingMode.BOX_ROUNDED, "$edge-segment-drawing-mode")
nx.set_edge_attributes(G, Style(color="red"), "$style")

print(ConsoleGraph(G))
