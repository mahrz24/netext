from netext import ConsoleGraph
from rich import print

g = ConsoleGraph(
    nodes={"Hello": {}, "World": {}},
    edges=[("Hello", "World")],
)

print(g)
