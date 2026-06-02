# Tutorial

## First Steps

To render a graph, create a [netext.ConsoleGraph][] with nodes and edges, then print it:

```python
from netext import ConsoleGraph
from rich import print

g = ConsoleGraph(
    nodes={"Hello": {}, "World": {}},
    edges=[("Hello", "World")],
)

print(g)
```

```{.rich title='Hello World' }
from netext import ConsoleGraph
from rich import print

output = ConsoleGraph(
    nodes={"Hello": {}, "World": {}},
    edges=[("Hello", "World")],
)
```

### Using networkx

networkx is not required to use Netext. If you already have a [networkx](https://networkx.org/) graph, install the optional extra with `pip install netext[networkx]` and use the `from_networkx` classmethod:

```python
from netext import ConsoleGraph
from rich import print

import networkx as nx

g = nx.Graph()
g.add_node("Hello")
g.add_node("World")
g.add_edge("Hello", "World")

print(ConsoleGraph.from_networkx(g))
```

## A Styled Graph

You can easily style the graph by adding attributes to the nodes and edges (see the [user guide about styling](./user-guide/styling-graphs.md)):

```python
from rich.style import Style
from rich import box, print

from netext import ConsoleGraph, EdgeRoutingMode

nodes = {
    "A": {"$content-style": Style(color="blue"), "$style": Style(color="red"), "$box-type": box.SQUARE},
    "B": {"$content-style": Style(color="blue"), "$style": Style(color="red"), "$box-type": box.SQUARE},
    "C": {"$content-style": Style(color="blue"), "$style": Style(color="red"), "$box-type": box.SQUARE},
}
edges = [
    ("A", "B", {"$style": Style(color="green")}),
    ("A", "C", {"$style": Style(color="green")}),
]

print(ConsoleGraph(nodes=nodes, edges=edges))
```


```{.rich title='Styled Graph' }
from rich.style import Style
from rich import box

from netext import ConsoleGraph, EdgeRoutingMode

nodes = {
    "A": {"$content-style": Style(color="blue"), "$style": Style(color="red"), "$box-type": box.SQUARE},
    "B": {"$content-style": Style(color="blue"), "$style": Style(color="red"), "$box-type": box.SQUARE},
    "C": {"$content-style": Style(color="blue"), "$style": Style(color="red"), "$box-type": box.SQUARE},
}
edges = [
    ("A", "B", {"$style": Style(color="green")}),
    ("A", "C", {"$style": Style(color="green")}),
]

output = ConsoleGraph(nodes=nodes, edges=edges)
```
