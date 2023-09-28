from netext import ConsoleGraph
from rich import print

import networkx as nx

g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")

print(ConsoleGraph(g))
