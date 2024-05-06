from netext import ConsoleGraph
from rich import print

import networkx as nx

g = nx.Graph()
g.add_node("Hello", **{"$x": 0, "$y": 0})
g.add_node("World", **{"$x": 0, "$y": 10})
g.add_edge("Hello", "World")

print(ConsoleGraph(g))
